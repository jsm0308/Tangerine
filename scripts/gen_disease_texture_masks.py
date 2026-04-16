#!/usr/bin/env python3
"""
병해 알베도 PNG 생성 (numpy+PIL). glTF용으로 미리 베이크한 2D 패턴.

  python scripts/gen_disease_texture_masks.py

산출: Generate_Tangerine_3D/procedural_track/textures/disease/{black_spot,canker,greening,scab}_albedo.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "Generate_Tangerine_3D" / "procedural_track" / "textures" / "disease"

# variants_batch.yaml disease_params 와 맞춤 (RGB 0–1)
def smoothstep(edge0, edge1, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / (edge1 - edge0 + 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


COLORS = {
    "healthy_base": np.array([0.85, 0.35, 0.05], dtype=np.float32),
    "black_spot_base": np.array([0.80, 0.32, 0.04], dtype=np.float32),
    "black_spot_spot": np.array([0.05, 0.02, 0.01], dtype=np.float32),
    "canker_base": np.array([0.78, 0.30, 0.04], dtype=np.float32),
    "canker_lesion": np.array([0.28, 0.12, 0.03], dtype=np.float32),
    "canker_halo": np.array([0.90, 0.78, 0.10], dtype=np.float32),
    "greening_orange": np.array([0.82, 0.32, 0.04], dtype=np.float32),
    "greening_green": np.array([0.12, 0.35, 0.04], dtype=np.float32),
    "scab_base": np.array([0.72, 0.28, 0.04], dtype=np.float32),
    "scab_patch": np.array([0.35, 0.22, 0.10], dtype=np.float32),
}


def _grid_uv(h: int, w: int) -> np.ndarray:
    u = np.linspace(0, 1, w, dtype=np.float32)
    v = np.linspace(0, 1, h, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)
    return np.stack([uu, vv], axis=-1)


def _voronoi_min_dist(uv: np.ndarray, n_seeds: int, rng: np.random.Generator) -> np.ndarray:
    """각 픽셀에서 가장 가까운 시드까지의 거리 (0~sqrt(2) 스케일)."""
    h, w, _ = uv.shape
    seeds = rng.random((n_seeds, 2)).astype(np.float32)
    flat = uv.reshape(-1, 1, 2)
    sd = seeds.reshape(1, n_seeds, 2)
    d = np.linalg.norm(flat - sd, axis=2)
    return d.min(axis=1).reshape(h, w)


def _smooth_noise(h: int, w: int, rng: np.random.Generator, scale: float = 6.0) -> np.ndarray:
    """간단한 옥타브 노이즈 (타일 느낌 완화)."""
    y = np.zeros((h, w), dtype=np.float32)
    amp, f = 1.0, 1
    for _ in range(4):
        sh, sw = max(2, h // f), max(2, w // f)
        small = rng.random((sh, sw)).astype(np.float32)
        yy = np.arange(h, dtype=np.float32) / h * (sh - 1)
        xx = np.arange(w, dtype=np.float32) / w * (sw - 1)
        yi = np.clip(yy.astype(int), 0, sh - 1)
        xi = np.clip(xx.astype(int), 0, sw - 1)
        y += amp * small[yi[:, None], xi[None, :]]
        amp *= 0.5
        f *= 2
    return (y - y.min()) / (y.max() - y.min() + 1e-6)


def make_black_spot(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    uv = _grid_uv(h, w)
    d = _voronoi_min_dist(uv, 220, rng)
    t = float(np.percentile(d, 88))
    spot = (d < t).astype(np.float32)
    spot = np.clip(spot + 0.15 * _smooth_noise(h, w, rng), 0, 1)
    spot = np.clip(spot, 0, 1)
    base = COLORS["black_spot_base"]
    sp = COLORS["black_spot_spot"]
    rgb = base[None, None, :] * (1 - spot[..., None]) + sp[None, None, :] * spot[..., None]
    return np.clip(rgb, 0, 1)


def make_canker(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    uv = _grid_uv(h, w)
    d = _voronoi_min_dist(uv, 45, rng)
    dn = (d - d.min()) / (d.max() - d.min() + 1e-6)
    # dn 작을수록 시드 근처 = 병변 중심; 클수록 건강 피부
    lesion = np.clip(1.0 - smoothstep(0.0, 0.12, dn), 0, 1)
    halo = np.clip(
        smoothstep(0.08, 0.26, dn) * (1.0 - smoothstep(0.0, 0.08, dn)),
        0,
        1,
    )
    healthy = np.clip(1.0 - lesion - halo, 0, 1)
    c0 = COLORS["canker_base"]
    c1 = COLORS["canker_lesion"]
    c2 = COLORS["canker_halo"]
    rgb = (
        c0 * healthy[..., None]
        + c1 * lesion[..., None]
        + c2 * halo[..., None]
    )
    return np.clip(rgb, 0, 1)


def make_greening(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    uv = _grid_uv(h, w)
    # 아래(v↑) 쪽 녹색 (줄기 방향 가정)
    v = uv[..., 1]
    ratio = 0.45
    stem = np.clip(1.0 - v / ratio, 0, 1)
    stem = smoothstep(0.0, 1.0, stem.astype(np.float32))
    n = _smooth_noise(h, w, rng, 6.0)
    mottle = 0.35 * (n - 0.5)
    fac = np.clip(stem + mottle, 0, 1)
    co = COLORS["greening_orange"]
    cg = COLORS["greening_green"]
    rgb = co[None, None, :] * (1 - fac[..., None]) + cg[None, None, :] * fac[..., None]
    return np.clip(rgb, 0, 1)


def make_scab(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    uv = _grid_uv(h, w)
    d = _voronoi_min_dist(uv, 90, rng)
    t = float(np.percentile(d, 72))
    patch = (d < t).astype(np.float32)
    patch = np.clip(patch + 0.2 * _smooth_noise(h, w, rng), 0, 1)
    base = COLORS["scab_base"]
    sc = COLORS["scab_patch"]
    rgb = base[None, None, :] * (1 - patch[..., None]) + sc[None, None, :] * patch[..., None]
    return np.clip(rgb, 0, 1)


def _save_rgb(name: str, arr: np.ndarray) -> None:
    u8 = (arr * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(u8, mode="RGB").save(name, compress_level=6)


def main() -> int:
    os.chdir(ROOT)
    rng = np.random.default_rng(42)
    h, w = 1024, 1024
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("black_spot_albedo.png", make_black_spot),
        ("canker_albedo.png", make_canker),
        ("greening_albedo.png", make_greening),
        ("scab_albedo.png", make_scab),
    ]
    for fname, fn in jobs:
        rgb = fn(h, w, rng)
        path = OUT_DIR / fname
        _save_rgb(str(path), rgb)
        print(f"[gen_disease_texture_masks] wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
