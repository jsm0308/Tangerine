"""Belt slot index from image coordinates (single-camera; offsets for multi-cam)."""

from __future__ import annotations

from typing import Optional, Tuple

from config import PipelineConfig


def camera_offset_slots(cfg: PipelineConfig) -> int:
    o = cfg.preprocess.multi_camera_offsets
    return int(o[0]) if o else 0


def bbox_center_xy(xyxy: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = xyxy
    return (0.5 * (x1 + x2), 0.5 * (y1 + y2))


def belt_slot_index(
    cx: float,
    image_width: int,
    slots_count: int,
    camera_offset_slots: int = 0,
) -> int:
    """Map horizontal center pixel to discrete slot index [0, slots_count)."""
    if slots_count <= 0:
        return 0
    w = max(1, image_width)
    slot = int(cx / float(w) * float(slots_count))
    slot = min(slots_count - 1, max(0, slot))
    return (slot + camera_offset_slots) % slots_count


def slot_for_box(
    bbox_xyxy: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    cfg: PipelineConfig,
) -> Optional[int]:
    """Return belt slot index or None if passthrough / disabled."""
    pre = cfg.preprocess
    if pre.mode == "passthrough" or not pre.attach_slots_during_inference:
        return None
    cx, _ = bbox_center_xy(bbox_xyxy)
    off = camera_offset_slots(cfg)
    return belt_slot_index(cx, image_width, pre.slots_count, off)
