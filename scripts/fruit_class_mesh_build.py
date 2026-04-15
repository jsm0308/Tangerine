#!/usr/bin/env python3
"""
data/Fruits/ 클래스 폴더별 GLB 배치 (기본 총 15개 = 5클래스 × 3).

- 베이스 메시: data/fresh_tangerine.glb, mandarin.glb, tangerine.glb
- 재질: 폴더 내 이미지 + 질병별 정점 색 (docs/DISEASE_MATERIALS.md)

  python scripts/fruit_class_mesh_build.py --config configs/default_config.yaml
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import load_pipeline_config, write_json  # noqa: E402

DEFAULT_MESHES = [
    ROOT / "data" / "fresh_tangerine.glb",
    ROOT / "data" / "mandarin.glb",
    ROOT / "data" / "tangerine.glb",
]


def _resolve_blender_exe(cfg) -> str:
    exe = (cfg.blender.blender_executable or "").strip()
    if exe:
        return exe
    return shutil.which("blender") or shutil.which("blender.exe") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="클래스별 질병 근사 GLB 배치")
    parser.add_argument("--config", default="configs/default_config.yaml")
    parser.add_argument("--fruits-root", type=Path, default=Path("data/Fruits"))
    parser.add_argument(
        "--total",
        type=int,
        default=15,
        help="생성할 GLB 총 개수 (클래스 수로 균등 분배)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="기본: outputs/{experiment_id}/fruit_class_batch",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    cfg_candidate = Path(args.config)
    if not cfg_candidate.is_absolute():
        cfg_candidate = ROOT / cfg_candidate
    cfg_path = str(cfg_candidate) if cfg_candidate.is_file() else None
    cfg = load_pipeline_config(cfg_path)
    os.chdir(ROOT)

    fruits_root = (ROOT / args.fruits_root).resolve()
    if not fruits_root.is_dir():
        print(f"없음: {fruits_root}", file=sys.stderr)
        return 1

    mesh_list = [p for p in DEFAULT_MESHES if p.is_file()]
    if len(mesh_list) != 3:
        print("data/ 에 GLB 3개 필요.", file=sys.stderr)
        return 1

    out = args.output
    if out is None:
        out = ROOT / cfg.experiment.base_output_dir / cfg.experiment.experiment_id / "fruit_class_batch"
    else:
        out = (ROOT / out).resolve() if not out.is_absolute() else out.resolve()

    blender_exe = _resolve_blender_exe(cfg)
    if not blender_exe:
        print("Blender 경로를 configs/default_config.yaml 에 설정하세요.", file=sys.stderr)
        return 1

    job = {
        "fruits_root": str(fruits_root),
        "mesh_paths": [str(p) for p in mesh_list],
        "output_root": str(out),
        "total_exports": int(args.total),
        "resume": bool(args.resume),
    }
    job_path = (
        ROOT / cfg.experiment.base_output_dir / cfg.experiment.experiment_id / "fruit_class_mesh_job.json"
    )
    job_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(job_path, job)

    entry = ROOT / "src" / "blender_sim" / "entries" / "fruit_class_mesh_entry.py"
    cmd = [blender_exe, "--background", "--python", str(entry), "--", str(job_path)]
    print("Blender:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"출력: {out}\n작업: {job_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
