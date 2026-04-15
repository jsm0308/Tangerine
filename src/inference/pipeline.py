"""
Multi-object detection + tracking + per-crop disease probabilities.

Backends (see `inference.detection_backend` in config):
- **yolo_two_stage** — YOLO detect + track + optional crop classifier (YOLO-cls or MobileNetV3).
- **yolo_unified** — single YOLO detector; disease from detector class ids mapped to `class_names`.
- **mask_rcnn_torchvision** — torchvision Mask R-CNN + IoU tracker + optional crop classifier.

Phase 1 belt slots: YAML `preprocess` + `slot_for_box` attach `belt_slot_index` when enabled
(implementation: `src/inference/preprocess/`).
"""

from __future__ import annotations

from pathlib import Path

from config import PipelineConfig

from src.inference.backends import dispatch_inference


def run_inference(cfg: PipelineConfig) -> Path:
    return dispatch_inference(cfg)
