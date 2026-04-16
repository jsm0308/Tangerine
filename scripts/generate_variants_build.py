#!/usr/bin/env python3
"""
Blender 헤드리스로 Generate_Tangerine_3D/procedural_track/configs/variants_batch.yaml 기준 변종 GLB 배치.

  python scripts/generate_variants_build.py --dry-run
  python scripts/generate_variants_build.py
  python scripts/generate_variants_build.py --config Generate_Tangerine_3D/procedural_track/configs/variants_batch.yaml
  python scripts/generate_variants_build.py --no-clean   # 기존 산출 유지

기본적으로 output_dir 를 비운 뒤 다시 빌드한다(프로토타입용). 유지하려면 --no-clean.

산출물: data/Tangerine_3D/glb_procedural/<클래스 폴더>/*.glb (트랙2 glb_from_2d 와 동일 폴더명), manifest.json
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


def _clean_output_dir(out_dir: Path) -> None:
    """프로토타입 재빌드: GLB·manifest·QC·하위 클래스 폴더 전부 제거(.gitkeep 유지)."""
    if not out_dir.is_dir():
        return
    for child in list(out_dir.iterdir()):
        if child.name == ".gitkeep":
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=False)
            else:
                child.unlink(missing_ok=True)
        except OSError as e:
            print(f"[clean] 건너뜀/실패: {child}: {e}", file=sys.stderr)
    print(f"[clean] 비움: {out_dir}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="generate_variants (Blender batch)")
    p.add_argument(
        "--config",
        default="Generate_Tangerine_3D/procedural_track/configs/variants_batch.yaml",
        help="변종 YAML",
    )
    p.add_argument(
        "--pipeline-config",
        default="configs/default_config.yaml",
        help="Blender 실행 파일 경로용 파이프라인 YAML",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--no-clean",
        action="store_true",
        help="빌드 전 output_dir 를 비우지 않음 (기본: 비움)",
    )
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
    if not args.dry_run and not args.no_clean:
        out_dir.mkdir(parents=True, exist_ok=True)
        _clean_output_dir(out_dir)
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
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    if not args.dry_run:
        org = ROOT / "scripts" / "organize_flat_variant_glbs.py"
        if org.is_file():
            subprocess.run([sys.executable, str(org), "--dir", str(out_dir)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
