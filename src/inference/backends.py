"""
Detection backend dispatch — `pipeline.run_inference` delegates here so backends stay in one module.
"""

from __future__ import annotations

from pathlib import Path

from config import PipelineConfig


def dispatch_inference(cfg: PipelineConfig) -> Path:
    """Run `inference.detection_backend` and return the predictions path."""
    backend = (cfg.inference.detection_backend or "yolo_two_stage").strip().lower()
    if backend in ("yolo_two_stage", "yolo_unified"):
        from src.inference.yolo_runner import run_yolo_inference

        return run_yolo_inference(cfg)
    if backend == "mask_rcnn_torchvision":
        from src.inference.mask_rcnn_runner import run_mask_rcnn_inference

        return run_mask_rcnn_inference(cfg)
    raise ValueError(
        f"Unknown inference.detection_backend: {cfg.inference.detection_backend!r}. "
        "Use yolo_two_stage, yolo_unified, or mask_rcnn_torchvision."
    )
