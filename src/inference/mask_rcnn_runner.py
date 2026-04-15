"""torchvision Mask R-CNN + IoU tracker + optional crop classifier."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
from src.inference.iou_tracker import IouTracker
from src.inference.preprocess import make_trigger, slot_for_box

logger = logging.getLogger(__name__)


def _normalize_prob_row(probs: np.ndarray, num_classes: int, class_names: List[str]) -> Tuple[List[float], int]:
    plist = probs[:num_classes].tolist() if len(probs) >= num_classes else list(probs) + [0.0] * (num_classes - len(probs))
    s = float(sum(plist)) or 1.0
    plist = [p / s for p in plist]
    top_idx = int(np.argmax(plist))
    return plist, top_idx


def run_mask_rcnn_inference(cfg: PipelineConfig) -> Path:
    apply_cuda_env(cfg.inference.cuda_visible_devices)
    import cv2
    import torch

    try:
        from torchvision.models.detection import maskrcnn_resnet50_fpn, MaskRCNN_ResNet50_FPN_Weights
    except ImportError as e:
        raise RuntimeError("mask_rcnn_torchvision requires torchvision. pip install torchvision") from e

    exp_dir = cfg.experiment_output_dir()
    img_dir = exp_dir / cfg.inference.inference_input_subdir
    if not img_dir.is_dir():
        raise FileNotFoundError(f"Inference image dir missing: {img_dir}")

    inf = cfg.inference
    device_s = inf.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_s)

    wpath = (inf.mask_rcnn_weights or "").strip()
    if wpath and Path(wpath).is_file():
        model = maskrcnn_resnet50_fpn(weights=None)
        try:
            state = torch.load(wpath, map_location="cpu", weights_only=True)
        except TypeError:
            state = torch.load(wpath, map_location="cpu")
        model.load_state_dict(state, strict=False)
    else:
        model = maskrcnn_resnet50_fpn(weights=MaskRCNN_ResNet50_FPN_Weights.COCO_V1)

    model.to(device)
    model.eval()

    num_classes = len(inf.class_names)
    cls_backend = (inf.classifier_backend or "yolo_cls").strip().lower()
    cls_model = None
    mobilenet_model = None
    mobilenet_dev = None
    if inf.mask_rcnn_classify_crops:
        if cls_backend == "yolo_cls" and inf.classifier_weights.strip() and Path(inf.classifier_weights).is_file():
            from ultralytics import YOLO

            cls_model = YOLO(inf.classifier_weights.strip())
        elif cls_backend == "mobilenet_v3":
            mobilenet_model, mobilenet_dev = load_mobilenet_v3_classifier(
                num_classes, inf.mobilenet_weights, device_s
            )
        elif cls_backend not in ("none",):
            logger.warning("mask_rcnn: unknown classifier_backend %s — uniform probs.", cls_backend)

    class_names = list(inf.class_names)
    out_path = exp_dir / inf.predictions_jsonl
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = sorted(img_dir.glob("frame_*.png"))
    if not frames:
        frames = sorted(img_dir.glob("*.png"))

    conf_th = float(inf.conf_threshold)
    bs = max(1, int(inf.batch_size_inference))
    crop_size = int(inf.cls_input_size)
    tracker = IouTracker(iou_threshold=float(inf.iou_threshold))
    trigger = make_trigger(cfg.preprocess.mode, cfg.preprocess.tick_stride_frames)
    slot_lines: List[str] = []
    slot_events_path = exp_dir / cfg.preprocess.slot_events_jsonl

    lines: List[str] = []
    for frame_path in frames:
        frame_idx = int(frame_path.stem.split("_")[-1]) if "_" in frame_path.stem else 0
        tick = trigger.tick_index_for_frame(frame_idx)
        img = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        t = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
        t = t.to(device)
        with torch.no_grad():
            outputs = model([t])[0]

        scores = outputs["scores"].detach().cpu().numpy()
        boxes_t = outputs["boxes"].detach().cpu().numpy()
        masks_t = outputs["masks"].detach().cpu().numpy() if "masks" in outputs else None

        keep = scores >= conf_th
        boxes_t = boxes_t[keep]
        scores = scores[keep]
        if masks_t is not None:
            masks_t = masks_t[keep]

        if len(boxes_t) == 0:
            rec = {"frame_index": frame_idx, "tick_index": tick, "image": frame_path.name, "objects": []}
            lines.append(json.dumps(rec, ensure_ascii=False))
            if cfg.preprocess.write_slot_events_jsonl:
                slot_lines.append(json.dumps({"frame_index": frame_idx, "tick_index": tick, "n_objects": 0}, ensure_ascii=False))
            continue

        tids = tracker.update(boxes_t.astype(np.float64))
        crops: List = []
        centroids: List[List[float]] = []
        for i in range(len(boxes_t)):
            crops.append(prepare_crop(img, boxes_t[i], crop_size))
            if masks_t is not None and i < masks_t.shape[0]:
                m = masks_t[i, 0]
                ys, xs = np.nonzero(m > 0.5)
                if len(xs) > 0:
                    centroids.append([float(xs.mean()), float(ys.mean())])
                else:
                    centroids.append([float((boxes_t[i][0] + boxes_t[i][2]) / 2), float((boxes_t[i][1] + boxes_t[i][3]) / 2)])
            else:
                bx = boxes_t[i]
                centroids.append([float((bx[0] + bx[2]) / 2), float((bx[1] + bx[3]) / 2)])

        if inf.mask_rcnn_classify_crops and cls_backend == "yolo_cls" and cls_model is not None:
            prob_chunks: List[np.ndarray] = []
            for start in range(0, len(crops), bs):
                batch = crops[start : start + bs]
                prob_chunks.append(classify_yolo_batch(cls_model, batch, device_s, num_classes))
            prob_rows = np.vstack(prob_chunks) if prob_chunks else np.zeros((0, num_classes))
        elif inf.mask_rcnn_classify_crops and cls_backend == "mobilenet_v3" and mobilenet_model is not None:
            prob_chunks = []
            for start in range(0, len(crops), bs):
                batch = crops[start : start + bs]
                prob_chunks.append(
                    classify_mobilenet_batch(mobilenet_model, mobilenet_dev, batch, crop_size, num_classes)
                )
            prob_rows = np.vstack(prob_chunks) if prob_chunks else np.zeros((0, num_classes))
        else:
            prob_rows = fallback_probs_batch(len(crops), num_classes)

        objects_out: List[Dict[str, Any]] = []
        for i in range(len(boxes_t)):
            probs = prob_rows[i]
            plist, top_idx = _normalize_prob_row(probs, num_classes, class_names)
            prob_dict = {class_names[j]: float(plist[j]) for j in range(min(len(class_names), len(plist)))}
            box = boxes_t[i].tolist()
            obj: Dict[str, Any] = {
                "track_id": int(tids[i]),
                "bbox_xyxy": box,
                "det_conf": float(scores[i]),
                "disease_probs": prob_dict,
                "top_disease": class_names[top_idx],
                "alert": float(plist[top_idx]) >= inf.alert_probability_threshold,
                "mask_centroid_xy": centroids[i],
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
