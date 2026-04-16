#!/usr/bin/env python3
"""
베이스 GLB 3종 생성 (단일 프리미티브, 꼭지 없음).

  python scripts/build_base_mesh.py
  python scripts/build_base_mesh.py --config Generate_Tangerine_3D/procedural_track/configs/base_mesh.yaml

설정: Generate_Tangerine_3D/procedural_track/configs/base_mesh.yaml
Blender: configs/default_config.yaml 의 blender_executable

산출: base_mesh.yaml 의 output_dir (기본 Generate_Tangerine_3D/procedural_track/mesh_bases/*.glb)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from config import load_pipeline_config  # noqa: E402


def _blender_exe(cfg) -> str:
    e = (cfg.blender.blender_executable or "").strip()
    if e and Path(e).is_file():
        return e
    return shutil.which("blender") or shutil.which("blender.exe") or ""


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build base fruit GLBs from Generate_Tangerine_3D/procedural_track/configs/base_mesh.yaml",
    )
    p.add_argument(
        "--config",
        default="Generate_Tangerine_3D/procedural_track/configs/base_mesh.yaml",
    )
    p.add_argument("--pipeline-config", default="configs/default_config.yaml")
    args = p.parse_args()

    os.chdir(ROOT)

    if yaml is None:
        print("PyYAML 필요: pip install pyyaml", file=sys.stderr)
        return 1

    ypath = Path(args.config)
    if not ypath.is_absolute():
        ypath = ROOT / ypath
    if not ypath.is_file():
        print(f"설정 없음: {ypath}", file=sys.stderr)
        return 1

    with open(ypath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    pc = Path(args.pipeline_config)
    if not pc.is_absolute():
        pc = ROOT / pc
    cfg = load_pipeline_config(str(pc) if pc.is_file() else None)
    exe = _blender_exe(cfg)
    if not exe:
        print("Blender 경로를 configs/default_config.yaml 에 설정하세요.", file=sys.stderr)
        return 1

    out_root = data.get("output_dir", "Generate_Tangerine_3D/procedural_track/mesh_bases")
    out_root_p = Path(out_root)
    if not out_root_p.is_absolute():
        out_root_p = (ROOT / out_root_p).resolve()

    defaults = data.get("defaults") or {}
    exports_out = []
    for exp in data.get("exports") or []:
        name = exp["asset_name"]
        merged = {**defaults, **exp}
        out_file = out_root_p / f"{name}.glb"
        exports_out.append(
            {
                **merged,
                "out_path": str(out_file),
                "asset_name": name,
            }
        )

    job = {
        "defaults": defaults,
        "material": data.get("material") or {},
        "exports": exports_out,
    }

    job_path = out_root_p / "_base_mesh_job.json"
    out_root_p.mkdir(parents=True, exist_ok=True)
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)

    entry = ROOT / "src" / "blender_sim" / "export_base_mesh.py"
    cmd = [exe, "--background", "--python", str(entry), "--", str(job_path.resolve())]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[build_base_mesh] 완료 → {out_root_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
