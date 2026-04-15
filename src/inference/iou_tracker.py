"""Greedy IoU-based multi-object tracking when Ultralytics track() is not used."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def _iou_xyxy(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    bb = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = aa + bb - inter + 1e-9
    return inter / union


class IouTracker:
    """Assign persistent IDs using per-frame greedy IoU matching."""

    def __init__(self, iou_threshold: float = 0.3) -> None:
        self.iou_threshold = iou_threshold
        self._next_id = 1
        self._prev_boxes: np.ndarray = np.zeros((0, 4), dtype=np.float64)
        self._prev_ids: np.ndarray = np.zeros((0,), dtype=np.int64)

    def update(self, xyxy: np.ndarray) -> np.ndarray:
        """
        Input: (N,4) xyxy. Returns (N,) integer track ids aligned with rows of xyxy.
        """
        n = xyxy.shape[0]
        if n == 0:
            self._prev_boxes = np.zeros((0, 4), dtype=np.float64)
            self._prev_ids = np.zeros((0,), dtype=np.int64)
            return np.zeros((0,), dtype=np.int64)

        if self._prev_boxes.shape[0] == 0:
            ids = np.arange(self._next_id, self._next_id + n, dtype=np.int64)
            self._next_id += n
            self._prev_boxes = xyxy.copy()
            self._prev_ids = ids.copy()
            return ids

        ious = np.zeros((n, self._prev_boxes.shape[0]), dtype=np.float64)
        for i in range(n):
            for j in range(self._prev_boxes.shape[0]):
                ious[i, j] = _iou_xyxy(xyxy[i], self._prev_boxes[j])

        used_prev = set()
        used_cur = set()
        pairs: List[Tuple[int, int]] = []
        flat = [(ious[i, j], i, j) for i in range(n) for j in range(self._prev_boxes.shape[0])]
        flat.sort(reverse=True, key=lambda t: t[0])
        for score, i, j in flat:
            if score < self.iou_threshold:
                break
            if i in used_cur or j in used_prev:
                continue
            used_cur.add(i)
            used_prev.add(j)
            pairs.append((i, j))

        ids = np.zeros(n, dtype=np.int64)
        for i, j in pairs:
            ids[i] = int(self._prev_ids[j])

        for i in range(n):
            if i in used_cur:
                continue
            ids[i] = self._next_id
            self._next_id += 1

        self._prev_boxes = xyxy.copy()
        self._prev_ids = ids.copy()
        return ids
