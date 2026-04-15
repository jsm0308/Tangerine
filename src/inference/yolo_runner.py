"""YOLO-based detection backends: unified (single model) and two-stage (det + classifier)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from config import PipelineConfig, apply_cuda_env
from src.inference.classifiers import (
    classify_mobilenet_batch,
    classify_yolo_batch,
    fallback_probs_batch,
    load_mobilenet_v3_classifier,
    prepare_crop,
    uniform_probs,
)
from src.inference.tracker_yaml import resolve_tracker_yaml
from src.inference.preprocess import make_trigger, slot_for_box

logger = logging.getLogger(__name__)


def _normalize_prob_row(probs: np.ndarray, num_classes: int, class_names: List[str]) -> Tuple[List[float], int]:
    plist = probs[:num_classes].tolist() if len(probs) >= num_classes else list(probs) + [0.0] * (num_classes - len(probs))
    s = float(sum(plist)) or 1.0
    plist = [p / s for p in plist]
    top_idx = int(np.argmax(plist))
    return plist, top_idx


def _probs_from_detector_classes(cls_ids: np.ndarray, num_classes: int) -> np.ndarray:
    n = len(cls_ids)
    out = np.zeros((n, num_classes), dtype=np.float64)
    for i in range(n):
        c = int(cls_ids[i])
        if 0 <= c < num_classes:
            out[i, c] = 1.0
        else:
            out[i] = uniform_probs(num_classes)
    return out


def run_yolo_inference(cfg: PipelineConfig) -> Path:
    apply_cuda_env(cfg.inference.cuda_visible_devices)
    from ultralytics import YOLO

    exp_dir = cfg.experiment_output_dir()
    img_dir = exp_dir / cfg.inference.inference_input_subdir
    if not img_dir.is_dir():
        raise FileNotFoundError(f"Inference image dir missing: {img_dir}")

    device = cfg.inference.device or None
    det = YOLO(cfg.inference.detector_weights)
    inf = cfg.inference
    backend = (inf.detection_backend or "yolo_two_stage").strip().lower()

    cls_backend = (inf.classifier_backend or "yolo_cls").strip().lower()
    cls_model = None
    mobilenet_model = None
    mobilenet_dev = None
    if backend == "yolo_two_stage":
        if cls_backend == "yolo_cls":
            cw = inf.classifier_weights.strip()
            if cw and Path(cw).is_file():
                cls_model = YOLO(cw)
            elif cw:
                logger.warning("classifier_weights path invalid — using uniform disease probabilities.")
            else:
                logger.warning("No classifier_weights — using uniform disease probabilities.")
        elif cls_backend == "mobilenet_v3":
            mobilenet_model, mobilenet_dev = load_mobilenet_v3_classifier(
                len(inf.class_names), inf.mobilenet_weights, device or ""
            )
        elif cls_backend not in ("yolo_cls", "mobilenet_v3", "none"):
            logger.warning("Unknown classifier_backend %s — using uniform.", cls_backend)

    class_names = list(inf.class_names)
    num_classes = len(class_names)
    out_path = exp_dir / inf.predictions_jsonl
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = sorted(img_dir.glob("frame_*.png"))
    if not frames:
        frames = sorted(img_dir.glob("*.png"))

    tracker_cfg = resolve_tracker_yaml(inf.tracker, inf.tracker_profile)
    conf = float(inf.conf_threshold)
    iou = float(inf.iou_threshold)
    bs = max(1, int(inf.batch_size_inference))
    crop_size = int(inf.cls_input_size)

    trigger = make_trigger(cfg.preprocess.mode, cfg.preprocess.tick_stride_frames)
    slot_lines: List[str] = []
    slot_events_path = exp_dir / cfg.preprocess.slot_events_jsonl

    lines: List[str] = []
    for frame_path in frames:
        frame_idx = int(frame_path.stem.split("_")[-1]) if "_" in frame_path.stem else 0
        tick = trigger.tick_index_for_frame(frame_idx)
        results = det.track(
            source=str(frame_path),
            conf=conf,
            iou=iou,
            tracker=tracker_cfg,
            persist=True,
            verbose=False,
            device=device,
        )
        if not results:
            continue
        r0 = results[0]
        img = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        boxes = r0.boxes
        if boxes is None or len(boxes) == 0:
            rec = {"frame_index": frame_idx, "tick_index": tick, "image": frame_path.name, "objects": []}
            lines.append(json.dumps(rec, ensure_ascii=False))
            if cfg.preprocess.write_slot_events_jsonl:
                slot_lines.append(json.dumps({"frame_index": frame_idx, "tick_index": tick, "n_objects": 0}, ensure_ascii=False))
            continue

        xyxy = boxes.xyxy.cpu().numpy()
        track_ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else np.arange(len(xyxy))
        det_confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(xyxy))
        det_cls = boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else None

        crops: List = []
        meta: List[Tuple[int, List[float], float]] = []
        for i in range(len(xyxy)):
            crops.append(prepare_crop(img, xyxy[i], crop_size))
            meta.append((int(track_ids[i]), xyxy[i].tolist(), float(det_confs[i])))

        if backend == "yolo_unified":
            if det_cls is not None and num_classes > 0:
                prob_rows = _probs_from_detector_classes(det_cls, num_classes)
            else:
                prob_rows = fallback_probs_batch(len(crops), num_classes)
        elif backend == "yolo_two_stage" and cls_backend == "none":
            prob_rows = fallback_probs_batch(len(crops), num_classes)
        elif backend == "yolo_two_stage" and cls_backend == "yolo_cls":
            prob_chunks: List[np.ndarray] = []
            for start in range(0, len(crops), bs):
                batch = crops[start : start + bs]
                if cls_model is not None:
                    pr = classify_yolo_batch(cls_model, batch, device, num_classes)
                    if pr.shape[1] != num_classes:
                        logger.warning(
                            "Classifier output dim %s != len(class_names) %s; check model vs config.",
                            pr.shape[1],
                            num_classes,
                        )
                else:
                    pr = fallback_probs_batch(len(batch), num_classes)
                prob_chunks.append(pr)
            prob_rows = np.vstack(prob_chunks) if prob_chunks else np.zeros((0, num_classes))
        elif backend == "yolo_two_stage" and cls_backend == "mobilenet_v3":
            prob_chunks = []
            for start in range(0, len(crops), bs):
                batch = crops[start : start + bs]
                if mobilenet_model is not None:
                    pr = classify_mobilenet_batch(
                        mobilenet_model, mobilenet_dev, batch, crop_size, num_classes
                    )
                else:
                    pr = fallback_probs_batch(len(batch), num_classes)
                prob_chunks.append(pr)
            prob_rows = np.vstack(prob_chunks) if prob_chunks else np.zeros((0, num_classes))
        else:
            prob_rows = fallback_probs_batch(len(crops), num_classes)

        objects_out: List[Dict[str, Any]] = []
        for i, (tid, box, dconf) in enumerate(meta):
            probs = prob_rows[i] if len(prob_rows) else uniform_probs(num_classes)
            plist, top_idx = _normalize_prob_row(probs, num_classes, class_names)
            prob_dict = {class_names[j]: float(plist[j]) for j in range(min(len(class_names), len(plist)))}
            obj: Dict[str, Any] = {
                "track_id": tid,
                "bbox_xyxy": box,
                "det_conf": dconf,
                "disease_probs": prob_dict,
                "top_disease": class_names[top_idx],
                "alert": float(plist[top_idx]) >= inf.alert_probability_threshold,
            }
            slot = slot_for_box(tuple(box), w, h, cfg)
            if slot is not None:
                obj["belt_slot_index"] = slot
            objects_out.append(obj)

        rec = {
            "frame_index": frame_idx,
            "tick_index": tick,
            "image": frame_path.name,
            "objects": objects_out,
        }
        lines.append(json.dumps(rec, ensure_ascii=False))
        if cfg.preprocess.write_slot_events_jsonl:
            slot_lines.append(
                json.dumps(
                    {
                        "frame_index": frame_idx,
                        "tick_index": tick,
                        "mm_per_tick": cfg.preprocess.mm_per_tick,
                        "n_objects": len(objects_out),
                    },
                    ensure_ascii=False,
                )
            )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    if cfg.preprocess.write_slot_events_jsonl and slot_lines:
        with open(slot_events_path, "w", encoding="utf-8") as f:
            f.write("\n".join(slot_lines) + "\n")
    logger.info("Wrote predictions: %s", out_path)
    return out_path
