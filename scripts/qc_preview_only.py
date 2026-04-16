#!/usr/bin/env python3
"""기존 변종 GLB에 대해 미리보기 PNG + 수치 QC만 실행(재빌드 없음)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_BLENDER_SIM = ROOT / "src" / "blender_sim"
if str(_BLENDER_SIM) not in sys.path:
    sys.path.insert(0, str(_BLENDER_SIM))

from disease_output_folder import disease_output_folder  # noqa: E402

from config import load_pipeline_config  # noqa: E402

_vqp = ROOT / "scripts" / "variant_qc_pipeline.py"
_spec = importlib.util.spec_from_file_location("variant_qc_pipeline", _vqp)
_vqc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_vqc)
qc_disease = _vqc.qc_disease
render_one = _vqc.render_one


def main() -> int:
    os.chdir(ROOT)
    pc = ROOT / "configs" / "default_config.yaml"
    cfg = load_pipeline_config(str(pc) if pc.is_file() else None)
    exe = (cfg.blender.blender_executable or "").strip()
    if exe and not Path(exe).is_file():
        exe = ""
    if not exe:
        exe = shutil.which("blender") or shutil.which("blender.exe") or ""
    if not exe:
        print("Blender 없음", file=sys.stderr)
        return 1

    out_dir = ROOT / "data" / "Tangerine_3D" / "glb_procedural"
    qc_dir = out_dir / "_qc_previews"
    qc_dir.mkdir(parents=True, exist_ok=True)
    base = "tangerine0"
    diseases = ["healthy", "black_spot", "canker", "greening", "scab"]
    ok_all = True
    for dis in diseases:
        glb = out_dir / disease_output_folder(dis) / f"{base}__{dis}.glb"
        png = qc_dir / f"qc_only_{dis}.png"
        if not glb.is_file():
            print(f"[skip] 없음: {glb.name}")
            continue
        render_one(exe, glb, png)
        ok, info = qc_disease(png, dis)
        print(f"{dis}: {'OK' if ok else 'FAIL'}  {info}")
        ok_all = ok_all and ok
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
