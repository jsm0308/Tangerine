"""
Apply motion blur, Gaussian noise, and JPEG compression per config.augment_order.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

from config import Augment2DConfig, PipelineConfig

logger = logging.getLogger(__name__)


def _odd_kernel(k: int) -> int:
    k = max(3, k)
    if k % 2 == 0:
        k += 1
    return k


def _motion_blur(img: np.ndarray, kernel_size: int, angle_deg: float) -> np.ndarray:
    k = _odd_kernel(kernel_size)
    kernel = np.zeros((k, k), dtype=np.float32)
    kernel[k // 2, :] = 1.0
    kernel /= kernel.sum()
    center = (k / 2.0 - 0.5, k / 2.0 - 0.5)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    rotated = cv2.warpAffine(kernel, M, (k, k))
    return cv2.filter2D(img, -1, rotated)


def _gaussian_noise(img: np.ndarray, std: float) -> np.ndarray:
    noise = np.random.normal(0, std, img.shape).astype(np.float32)
    out = img.astype(np.float32) + noise
    return np.clip(out, 0, 255).astype(np.uint8)


def _jpeg_compress(img: np.ndarray, quality: int) -> np.ndarray:
    q = int(np.clip(quality, 1, 100))
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    if not ok:
        return img
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def augment_image(
    img_bgr: np.ndarray,
    cfg: Augment2DConfig,
    belt_blur_angle_deg: float,
) -> np.ndarray:
    """Apply augment_order sequence to one BGR image."""
    out = img_bgr.copy()
    angle = belt_blur_angle_deg if cfg.blur_direction_tied_to_belt else cfg.belt_blur_angle_deg
    for step in cfg.augment_order:
        if step == "motion_blur":
            if np.random.random() < cfg.motion_blur_probability:
                k = _odd_kernel(cfg.motion_blur_max_kernel)
                out = _motion_blur(out, k, angle)
        elif step == "gaussian_noise":
            std = float(np.random.uniform(cfg.gaussian_noise_std_min, cfg.gaussian_noise_std_max))
            if std > 0:
                out = _gaussian_noise(out, std)
        elif step == "jpeg":
            q = int(np.random.randint(cfg.jpeg_quality_min, cfg.jpeg_quality_max + 1))
            out = _jpeg_compress(out, q)
        else:
            logger.warning("Unknown augment step: %s", step)
    return out


def run_augmentation(cfg: PipelineConfig) -> Path:
    """Read PNGs from input_subdir, write augmented PNGs to output_subdir."""
    exp_dir = cfg.experiment_output_dir()
    inp = exp_dir / cfg.augment.input_subdir
    out = exp_dir / cfg.augment.output_subdir
    out.mkdir(parents=True, exist_ok=True)
    if not inp.is_dir():
        raise FileNotFoundError(f"Augment input dir missing: {inp}")

    paths = sorted(inp.glob("frame_*.png"))
    if not paths:
        paths = sorted(inp.glob("*.png"))
    if not paths:
        logger.warning("No PNG frames in %s", inp)
        return out

    np.random.seed(cfg.experiment.seed)
    belt_angle = 0.0  # horizontal belt → blur along rows
    for p in paths:
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Skip unreadable: %s", p)
            continue
        aug = augment_image(img, cfg.augment, belt_angle)
        dst = out / p.name
        cv2.imwrite(str(dst), aug)
    logger.info("Augmented %d frames -> %s", len(paths), out)
    return out
