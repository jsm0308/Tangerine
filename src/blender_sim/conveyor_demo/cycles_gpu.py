"""Cycles에서 GPU(OPTIX/CUDA 등) 사용 시도 — 실패 시 CPU."""

from __future__ import annotations

from typing import Any, Dict

import bpy


def configure_cycles_device(scene: bpy.types.Scene, cfg: Dict[str, Any]) -> None:
    want = str(cfg.get("cycles_compute_device", "GPU")).upper()
    if want != "GPU":
        if hasattr(scene.cycles, "device"):
            scene.cycles.device = "CPU"
        return

    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except Exception:
        if hasattr(scene.cycles, "device"):
            scene.cycles.device = "CPU"
        return

    # Windows NVIDIA: OPTIX 우선, 그다음 CUDA
    for ctype in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = ctype
            break
        except (TypeError, ValueError, KeyError, AttributeError):
            continue

    try:
        for dev in prefs.devices:
            if dev.type != "CPU":
                dev.use = True
            else:
                dev.use = False
    except Exception:
        pass

    if hasattr(scene.cycles, "device"):
        try:
            scene.cycles.device = "GPU"
        except Exception:
            scene.cycles.device = "CPU"
