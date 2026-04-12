#!/usr/bin/env python3
"""
81 healthy 형태 변형 GLB (3 베이스 × 3 크기 × 3 납작 × 3 울퉁) + **healthy 폴더 첫 이미지** 텍스처.

산출물: `outputs/{experiment_id}/healthy_variants_glb/*.glb`

향후: 모든 이미지 × 81 형태 = 이미지수×81 GLB 로 확장 (동일 `healthy_variants_export` 그리드).

  python scripts/healthy_variants_build.py --config configs/default_config.yaml
  python scripts/healthy_variants_build.py --texture data/Fruits/healthy/foo.jpg
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

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

DEFAULT_MESHES = [
    ROOT / "data" / "fresh_tangerine.glb",
    ROOT / "data" / "mandarin.glb",
    ROOT / "data" / "tangerine.glb",
]


def _first_image_in_healthy(fruits_root: Path) -> Path:
    """`.../healthy` 또는 `.../Healthy` 바로 아래 파일만 (재귀 없음), 이름 정렬 후 첫 장."""
    for sub in ("healthy", "Healthy"):
        d = fruits_root / sub
        if not d.is_dir():
            continue
        files = sorted(
            p
            for p in d.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXT
        )
        if files:
            return files[0].resolve()
    raise FileNotFoundError(
        f"healthy 또는 Healthy 폴더에 이미지가 없습니다: {fruits_root}"
    )


def _resolve_blender_exe(cfg) -> str:
    exe = (cfg.blender.blender_executable or "").strip()
    if exe:
        return exe
    return shutil.which("blender") or shutil.which("blender.exe") or ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="81 healthy 형태 GLB (첫 healthy 이미지 텍스처)"
    )
    parser.add_argument("--config", default="configs/default_config.yaml")
    parser.add_argument(
        "--fruits-root",
        type=Path,
        default=Path("data/Fruits"),
        help="healthy 하위 폴더를 찾을 루트",
    )
    parser.add_argument(
        "--texture",
        type=Path,
        default=None,
        help="텍스처 이미지 직접 지정 (미지정 시 healthy/ 첫 파일)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="기본: outputs/{experiment_id}/healthy_variants_glb",
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
    if args.texture is not None:
        tex = (ROOT / args.texture).resolve() if not args.texture.is_absolute() else args.texture.resolve()
    else:
        tex = _first_image_in_healthy(fruits_root)

    if not tex.is_file():
        print(f"텍스처 없음: {tex}", file=sys.stderr)
        return 1

    mesh_list = [p for p in DEFAULT_MESHES if p.is_file()]
    if len(mesh_list) != 3:
        print(
            "data/ 에 fresh_tangerine.glb, mandarin.glb, tangerine.glb 세 개가 필요합니다.",
            file=sys.stderr,
        )
        return 1

    out = args.output
    if out is None:
        out = ROOT / cfg.experiment.base_output_dir / cfg.experiment.experiment_id / "healthy_variants_glb"
    else:
        out = (ROOT / out).resolve() if not out.is_absolute() else out.resolve()

    print(f"텍스처: {tex}")
    print(f"베이스 메시: {[p.name for p in mesh_list]}")
    print(f"출력: {out}")

    blender_exe = _resolve_blender_exe(cfg)
    if not blender_exe:
        print("Blender 실행 파일을 찾을 수 없습니다. configs/default_config.yaml 의 blender.blender_executable 설정.", file=sys.stderr)
        return 1

    job = {
        "mesh_paths": [str(p) for p in mesh_list],
        "texture_path": str(tex),
        "output_root": str(out),
        "resume": bool(args.resume),
    }
    job_path = (
        ROOT / cfg.experiment.base_output_dir / cfg.experiment.experiment_id / "healthy_variants_job.json"
    )
    job_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(job_path, job)

    entry = ROOT / "src" / "blender_sim" / "healthy_variants_entry.py"
    cmd = [blender_exe, "--background", "--python", str(entry), "--", str(job_path)]
    print("Blender:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"작업 정의: {job_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
