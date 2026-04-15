"""Shared detection batch types for modular backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


@dataclass
class DetectionBatch:
    """One frame worth of detector outputs (before or after tracking)."""

    xyxy: np.ndarray  # (N, 4) float
    conf: np.ndarray  # (N,) float
    class_ids: Optional[np.ndarray] = None
    masks: Optional[Any] = None
    mask_centroids_xy: Optional[np.ndarray] = None


def empty_batch() -> DetectionBatch:
    return DetectionBatch(
        xyxy=np.zeros((0, 4), dtype=np.float64),
        conf=np.zeros((0,), dtype=np.float64),
    )
