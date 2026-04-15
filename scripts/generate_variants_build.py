#!/usr/bin/env python3
"""
Blender 헤드리스로 data/Tangerine_3D/configs/variants_batch.yaml 기준 변종 GLB 배치.

  python scripts/generate_variants_build.py --dry-run
  python scripts/generate_variants_build.py
  python scripts/generate_variants_build.py --config data/Tangerine_3D/configs/variants_batch.yaml

산출물: outputs/_variant_glb/*.glb (기본 output_dir; YAML에서 변경 가능), manifest.json
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
    p = argparse.ArgumentParser(description="generate_variants (Blender batch)")
    p.add_argument(
        "--config",
        default="data/Tangerine_3D/configs/variants_batch.yaml",
        help="변종 YAML",
    )
    p.add_argument(
        "--pipeline-config",
        default="configs/default_config.yaml",
        help="Blender 실행 파일 경로용 파이프라인 YAML",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    os.chdir(ROOT)

    pc = Path(args.pipeline_config)
    if not pc.is_absolute():
        pc = ROOT / pc
    cfg = load_pipeline_config(str(pc) if pc.is_file() else None)

    exe = _blender_exe(cfg)
    if not exe:
        print("Blender 를 찾을 수 없습니다. configs/default_config.yaml 의 blender.blender_executable 을 설정하세요.", file=sys.stderr)
        return 1

    vc = Path(args.config)
    if not vc.is_absolute():
        vc = ROOT / vc
    if not vc.is_file():
        print(f"변종 설정 없음: {vc}", file=sys.stderr)
        return 1

    if yaml is None:
        print("PyYAML 필요: pip install pyyaml", file=sys.stderr)
        return 1

    with open(vc, "r", encoding="utf-8") as f:
        variant_data = yaml.safe_load(f)

    # 프로젝트 루트 기준 경로 해석 → Blender가 그대로 쓰도록 절대 경로로 고정
    def _abs(p: str) -> str:
        pp = Path(p)
        return str(pp.resolve() if pp.is_absolute() else (ROOT / pp).resolve())

    variant_data["output_dir"] = _abs(variant_data["output_dir"])
    for src in variant_data.get("glb_sources") or []:
        src["path"] = _abs(src["path"])

    out_dir = Path(variant_data["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    job_path = out_dir / "_resolved_job.json"
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(variant_data, f, indent=2, ensure_ascii=False)

    entry = ROOT / "src" / "blender_sim" / "generate_variants.py"
    extra = ["--dry-run"] if args.dry_run else []
    cmd = [
        exe,
        "--background",
        "--factory-startup",
        "--python",
        str(entry),
        "--",
        "--job-json",
        str(job_path.resolve()),
        *extra,
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
