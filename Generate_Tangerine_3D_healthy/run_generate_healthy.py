#!/usr/bin/env python3
"""
Healthy 변종 GLB 배치 (패키지 단독 실행).

  압축을 풀은 폴더에서:
    pip install pyyaml
    # data/Tangerine_3D/tangerine_0.glb ~ tangerine_2.glb 배치 후
    python run_generate_healthy.py --dry-run
    python run_generate_healthy.py --no-clean

환경 변수:
  BLENDER_EXE  — Blender 바이너리 전체 경로 (미설정 시 PATH 의 blender)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _blender_exe() -> str:
    e = (os.environ.get("BLENDER_EXE") or "").strip()
    if e and Path(e).is_file():
        return e
    w = shutil.which("blender") or shutil.which("blender.exe")
    return w or ""


def _clean_output_dir(out_dir: Path) -> None:
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
    try:
        import yaml  # type: ignore
    except ImportError:
        print("PyYAML 필요: pip install pyyaml", file=sys.stderr)
        return 1

    p = argparse.ArgumentParser(description="healthy variant GLB (Blender batch)")
    p.add_argument(
        "--config",
        default="configs/variants_batch_healthy.yaml",
        help="변종 YAML (패키지 루트 기준)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--no-clean",
        action="store_true",
        help="빌드 전 output_dir 비우지 않음",
    )
    args = p.parse_args()

    os.chdir(ROOT)

    exe = _blender_exe()
    if not exe:
        print(
            "Blender 를 찾을 수 없습니다. apt install blender 또는 BLENDER_EXE=/path/to/blender",
            file=sys.stderr,
        )
        return 1

    vc = Path(args.config)
    if not vc.is_absolute():
        vc = ROOT / vc
    if not vc.is_file():
        print(f"변종 설정 없음: {vc}", file=sys.stderr)
        return 1

    with open(vc, "r", encoding="utf-8") as f:
        variant_data = yaml.safe_load(f)

    def _abs(path_str: str) -> str:
        pp = Path(path_str)
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
