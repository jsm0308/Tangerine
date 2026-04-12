"""
Multi-object detection + tracking + per-crop full class probabilities.

Design (locked):
- **Detector** (Ultralytics `task=detect`): bounding boxes + track IDs (ByteTrack/BoT-SORT via `tracker=`).
- **Classifier** (Ultralytics `task=classify`, optional): softmax vector aligned with `config.inference.class_names`.
  If weights are missing, probabilities are uniform so the pipeline still runs end-to-end.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import PipelineConfig, apply_cuda_env

logger = logging.getLogger(__name__)


def _uniform_probs(n: int) -> np.ndarray:
    return np.ones(n, dtype=np.float64) / max(1, n)


def _classify_batch(
    cls_model: Any,
    crops_bgr: List[np.ndarray],
    device: Optional[str],
    num_classes: int,
) -> np.ndarray:
    """Returns (N, num_classes) softmax rows."""
    if not crops_bgr:
        return np.zeros((0, 0), dtype=np.float64)
    # Ultralytics classification accepts list of ndarray
    results = cls_model.predict(crops_bgr, verbose=False, device=device or None)
    rows: List[np.ndarray] = []
    for r in results:
        if r.probs is not None:
            t = r.probs.data
            if hasattr(t, "cpu"):
                t = t.cpu().numpy()
            rows.append(np.asarray(t).ravel())
        else:
            rows.append(_uniform_probs(num_classes))
    return np.stack(rows, axis=0)


def _fallback_probs_batch(n: int, num_classes: int) -> np.ndarray:
    u = _uniform_probs(num_classes)
    return np.tile(u, (n, 1))


def _prepare_crop(img: np.ndarray, xyxy: np.ndarray, size: int) -> np.ndarray:
    x1, y1, x2, y2 = [int(round(x)) for x in xyxy]
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        crop = np.zeros((size, size, 3), dtype=np.uint8)
    else:
        crop = img[y1:y2, x1:x2]
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)


def run_inference(cfg: PipelineConfig) -> Path:
    apply_cuda_env(cfg.inference.cuda_visible_devices)
    from ultralytics import YOLO

    exp_dir = cfg.experiment_output_dir()
    img_dir = exp_dir / cfg.inference.inference_input_subdir
    if not img_dir.is_dir():
        raise FileNotFoundError(f"Inference image dir missing: {img_dir}")

    device = cfg.inference.device or None
    det = YOLO(cfg.inference.detector_weights)
    cls_weights = cfg.inference.classifier_weights.strip()
    cls_model = YOLO(cls_weights) if cls_weights and Path(cls_weights).is_file() else None
    if not cls_weights:
        logger.warning("No classifier_weights — using uniform disease probabilities.")
    elif cls_model is None:
        logger.warning("classifier_weights path invalid — using uniform disease probabilities.")

    class_names = list(cfg.inference.class_names)
    num_classes = len(class_names)
    out_path = exp_dir / cfg.inference.predictions_jsonl
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = sorted(img_dir.glob("frame_*.png"))
    if not frames:
        frames = sorted(img_dir.glob("*.png"))

    tracker_cfg = cfg.inference.tracker
    conf = float(cfg.inference.conf_threshold)
    iou = float(cfg.inference.iou_threshold)
    bs = max(1, int(cfg.inference.batch_size_inference))
    crop_size = int(cfg.inference.cls_input_size)

    lines: List[str] = []
    # Persist tracks across frames
    for frame_path in frames:
        frame_idx = int(frame_path.stem.split("_")[-1]) if "_" in frame_path.stem else 0
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
        boxes = r0.boxes
        if boxes is None or len(boxes) == 0:
            rec = {
                "frame_index": frame_idx,
                "image": frame_path.name,
                "objects": [],
            }
            lines.append(json.dumps(rec, ensure_ascii=False))
            continue

        xyxy = boxes.xyxy.cpu().numpy()
        track_ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else np.arange(len(xyxy))
        det_confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(xyxy))

        crops: List[np.ndarray] = []
        meta: List[Tuple[int, np.ndarray, float]] = []
        for i in range(len(xyxy)):
            crops.append(_prepare_crop(img, xyxy[i], crop_size))
            meta.append((int(track_ids[i]), xyxy[i].tolist(), float(det_confs[i])))

        prob_chunks: List[np.ndarray] = []
        for start in range(0, len(crops), bs):
            batch = crops[start : start + bs]
            if cls_model is not None:
                pr = _classify_batch(cls_model, batch, device, num_classes)
                if pr.shape[1] != num_classes:
                    logger.warning(
                        "Classifier output dim %s != len(class_names) %s; check model vs config.",
                        pr.shape[1],
                        num_classes,
                    )
            else:
                pr = _fallback_probs_batch(len(batch), num_classes)
            prob_chunks.append(pr)
        prob_rows = np.vstack(prob_chunks) if prob_chunks else np.zeros((0, num_classes))

        objects_out: List[Dict[str, Any]] = []
        for i, (tid, box, dconf) in enumerate(meta):
            probs = prob_rows[i] if prob_rows is not None else _uniform_probs(num_classes)
            # Align length to class_names
            plist = probs[:num_classes].tolist() if len(probs) >= num_classes else list(probs) + [0.0] * (
                num_classes - len(probs)
            )
            s = float(sum(plist)) or 1.0
            plist = [p / s for p in plist]
            prob_dict = {class_names[j]: float(plist[j]) for j in range(min(len(class_names), len(plist)))}
            top_idx = int(np.argmax(plist))
            objects_out.append(
                {
                    "track_id": tid,
                    "bbox_xyxy": box,
                    "det_conf": dconf,
                    "disease_probs": prob_dict,
                    "top_disease": class_names[top_idx],
                    "alert": float(plist[top_idx]) >= cfg.inference.alert_probability_threshold,
                }
            )

        rec = {
            "frame_index": frame_idx,
            "image": frame_path.name,
            "objects": objects_out,
        }
        lines.append(json.dumps(rec, ensure_ascii=False))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    logger.info("Wrote predictions: %s", out_path)
    return out_path
