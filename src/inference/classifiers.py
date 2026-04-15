"""Crop classifiers: Ultralytics YOLO-cls and torchvision MobileNetV3."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def uniform_probs(n: int) -> np.ndarray:
    return np.ones(n, dtype=np.float64) / max(1, n)


def classify_yolo_batch(
    cls_model: Any,
    crops_bgr: List[np.ndarray],
    device: Optional[str],
    num_classes: int,
) -> np.ndarray:
    """Returns (N, num_classes) softmax rows."""
    if not crops_bgr:
        return np.zeros((0, 0), dtype=np.float64)
    results = cls_model.predict(crops_bgr, verbose=False, device=device or None)
    rows: List[np.ndarray] = []
    for r in results:
        if r.probs is not None:
            t = r.probs.data
            if hasattr(t, "cpu"):
                t = t.cpu().numpy()
            rows.append(np.asarray(t).ravel())
        else:
            rows.append(uniform_probs(num_classes))
    return np.stack(rows, axis=0)


def fallback_probs_batch(n: int, num_classes: int) -> np.ndarray:
    u = uniform_probs(num_classes)
    return np.tile(u, (n, 1))


def prepare_crop(img: np.ndarray, xyxy: np.ndarray, size: int) -> np.ndarray:
    x1, y1, x2, y2 = [int(round(x)) for x in xyxy]
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        crop = np.zeros((size, size, 3), dtype=np.uint8)
    else:
        crop = img[y1:y2, x1:x2]
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)


def load_mobilenet_v3_classifier(num_classes: int, weights_path: str, device: str):
    """MobileNetV3-Small with replaced classifier head; optional .pth weights."""
    import torch
    import torch.nn as nn
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    wpath = (weights_path or "").strip()
    if wpath and Path(wpath).is_file():
        m = mobilenet_v3_small(weights=None)
        in_f = m.classifier[3].in_features
        m.classifier[3] = nn.Linear(in_f, num_classes)
        try:
            state = torch.load(wpath, map_location="cpu", weights_only=True)
        except TypeError:
            state = torch.load(wpath, map_location="cpu")
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        m.load_state_dict(state, strict=False)
    else:
        m = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        in_f = m.classifier[3].in_features
        m.classifier[3] = nn.Linear(in_f, num_classes)
        if wpath:
            logger.warning("mobilenet_weights path invalid — using ImageNet backbone + random head.")

    m.eval()
    dev = torch.device(device or ("cuda" if __import__("torch").cuda.is_available() else "cpu"))
    m.to(dev)
    return m, dev


def classify_mobilenet_batch(
    model: Any,
    device: Any,
    crops_bgr: List[np.ndarray],
    input_size: int,
    num_classes: int,
) -> np.ndarray:
    import torch
    import torch.nn.functional as F

    if not crops_bgr:
        return np.zeros((0, num_classes), dtype=np.float64)
    mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)
    tensors = []
    for c in crops_bgr:
        rgb = cv2.cvtColor(c, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        t = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
        t = F.interpolate(t, size=(input_size, input_size), mode="bilinear", align_corners=False)
        tensors.append(t)
    batch = torch.cat(tensors, dim=0).to(device)
    batch = (batch - mean) / std
    with torch.no_grad():
        logits = model(batch)
        probs = torch.softmax(logits, dim=1)
    return probs.cpu().numpy()
