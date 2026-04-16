#!/usr/bin/env python3
"""
프로시저 컨베이어(롤러·데크·레일·다리·바구니 등)를 `defaults.py`와 동일한 규격으로 빌드해 GLB로 내보냄.

  python Conveyor_Lab/scripts/export_conveyor_glb.py
  python Conveyor_Lab/scripts/export_conveyor_glb.py --out Generate_Tangerine_3D/procedural_track/mesh_bases/conveyor_belt.glb
  python Conveyor_Lab/scripts/export_conveyor_glb.py --overrides my_overrides.json

기울기는 `defaults.py` 의 `conveyor_pitch_deg` 등(또는 overrides JSON)과 동일하게 적용됩니다.

Blender 서브프로세스가 `src/blender_sim/entries/conveyor_glb_export_entry.py` 를 실행합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "src" / "blender_sim" / "entries" / "conveyor_glb_export_entry.py"
_DEFAULT_GLB = ROOT / "Conveyor_Lab" / "outputs" / "glb" / "conveyor_belt.glb"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.blender_sim.conveyor.defaults import merge_config  # noqa: E402


def _find_blender_executable() -> str | None:
    for key in ("BLENDER_EXECUTABLE", "BLENDER"):
        v = (os.environ.get(key) or "").strip().strip('"')
        if v and Path(v).is_file():
            return v
    for name in ("blender", "blender.exe"):
        w = shutil.which(name)
        if w:
            return w
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    bf = program_files / "Blender Foundation"
    if bf.is_dir():
        subs = sorted((p for p in bf.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
        for sub in subs:
            exe = sub / "blender.exe"
            if exe.is_file():
                return str(exe)
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Export procedural conveyor as GLB (Blender)")
    p.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_GLB,
        help="Output .glb path (default: Conveyor_Lab/outputs/glb/conveyor_belt.glb)",
    )
    p.add_argument(
        "--overrides",
        type=Path,
        default=None,
        help="Optional JSON with keys from conveyor defaults (belt_length_m, roller_count, ...)",
    )
    p.add_argument("--blender", type=str, default="", help="Blender executable path")
    args = p.parse_args()

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    exe = (args.blender or "").strip() or _find_blender_executable()
    if not exe:
        print("Blender not found. Set PATH, BLENDER_EXECUTABLE, or --blender.", file=sys.stderr)
        return 3

    overrides: dict = {
        "output_dir": str(out.parent),
        "export_glb_filename": out.name,
    }
    if args.overrides and args.overrides.is_file():
        with open(args.overrides, "r", encoding="utf-8") as f:
            extra = json.load(f)
        if not isinstance(extra, dict):
            print("--overrides must be a JSON object", file=sys.stderr)
            return 2
        overrides.update(extra)

    cfg = merge_config(overrides)
    cfg_path = out.parent / "conveyor_glb_export.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    cmd = [exe, "--background", "--factory-startup", "--python", str(ENTRY), "--", str(cfg_path)]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"Done: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
