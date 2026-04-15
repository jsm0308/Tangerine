"""프레임별 투입 스케줄 및 스폰 위치."""

from __future__ import annotations

import random
from typing import Any, Dict, List

from mathutils import Vector


def _compute_spawn_frames_uniform(total: int, episode_frames: int) -> List[int]:
    """에피소드 전체에 고르게 분산 (1-based), 프레임당 최대 1개."""
    if total <= 0:
        return []
    last = max(2, episode_frames - 1)
    if total == 1:
        return [1]
    raw = [1 + int((last - 1) * i / (total - 1)) for i in range(total)]
    out: List[int] = []
    prev = 0
    for f in raw:
        f = max(prev + 1, min(f, last))
        if f > last:
            break
        out.append(f)
        prev = f
    return out


def _compute_spawn_frames_batched(total: int, episode_frames: int, cfg: Dict[str, Any]) -> List[int]:
    """몇 개씩 묶어서 천천히 투입: 배치 안에서는 짧은 간격, 배치 사이는 긴 휴지."""
    if total <= 0:
        return []
    last = max(2, episode_frames - 1)
    batch = max(1, int(cfg.get("spawn_batch_size", 3)))
    gap_batch = max(0, int(cfg.get("spawn_batch_gap_frames", 40)))
    gap_intra = max(1, int(cfg.get("spawn_intra_batch_gap_frames", 6)))
    start = max(2, int(cfg.get("spawn_start_frame", 24)))

    frames: List[int] = []
    f = start
    while len(frames) < total and f <= last:
        for _ in range(batch):
            if len(frames) >= total:
                break
            if f > last:
                break
            frames.append(f)
            f += gap_intra
        f += gap_batch

    if len(frames) < total:
        # 에피소드가 짧으면(설정 실수) 균등 분포로 대체해 개수를 맞춤
        return _compute_spawn_frames_uniform(total, episode_frames)
    return frames


def compute_spawn_frames(total: int, episode_frames: int, cfg: Dict[str, Any] | None = None) -> List[int]:
    """
    스폰 프레임 목록 (1-based).

    `spawn_schedule_mode`:
    - ``batched`` (기본): `spawn_batch_size` 개씩, `spawn_intra_batch_gap_frames` 간격으로 떨어뜨리고
      각 묶음 사이에 `spawn_batch_gap_frames` 만큼 비움.
    - ``uniform``: 에피소드 전체에 균등 분포 (기존 동작).
    """
    c = cfg or {}
    mode = (c.get("spawn_schedule_mode") or "batched").lower()
    if mode == "uniform":
        return _compute_spawn_frames_uniform(total, episode_frames)
    return _compute_spawn_frames_batched(total, episode_frames, c)


def spawn_location_for_frame(
    cfg: Dict[str, Any],
    spawn_min: Vector,
    spawn_max: Vector,
    rng: random.Random,
) -> Vector:
    """
    롤러 베드 바운딩(spawn_min/max) 위에서만 스폰.
    벨트 길이 방향(X)으로 인입 — 모터/체인이 포함된 전체 belt_bounds 쓰지 않음.
    """
    edge = (cfg.get("spawn_edge") or "min_x").lower()
    pad_x = float(cfg.get("spawn_pad_along_belt_m", 0.08))
    intensity = float(cfg.get("spawn_drop_intensity", 1.0))
    intensity = max(0.05, min(1.5, intensity))
    jy = float(cfg.get("spawn_y_jitter_m", 0.04)) * min(1.0, intensity + 0.15)
    hz = float(cfg.get("spawn_height_above_rollers_m", 0.045)) * intensity
    y_edge = float(cfg.get("spawn_y_edge_margin_m", 0.03))

    cy = (spawn_min.y + spawn_max.y) * 0.5
    y_lo = spawn_min.y + y_edge
    y_hi = spawn_max.y - y_edge
    if y_lo < y_hi:
        half = min(jy, (y_hi - y_lo) * 0.45)
        y = cy + rng.uniform(-half, half)
        y = max(y_lo, min(y_hi, y))
    else:
        y = cy

    if edge == "max_x":
        x = spawn_max.x - pad_x
    else:
        x = spawn_min.x + pad_x

    z = spawn_max.z + hz
    return Vector((x, y, z))
