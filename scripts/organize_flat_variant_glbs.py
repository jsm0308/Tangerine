#!/usr/bin/env python3
"""
glb_procedural 루트에 남아 있는 tangerine*__.glb 를 병해 클래스 폴더로 이동한다.

  python scripts/organize_flat_variant_glbs.py
  python scripts/organize_flat_variant_glbs.py --dir data/Tangerine_3D/glb_from_2d

이전 빌드(루트에 직접 쌓이던 방식) 정리용. generate_variants_build.py 끝에서도 한 번 호출한다.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_BLENDER_SIM = ROOT / "src" / "blender_sim"
if str(_BLENDER_SIM) not in sys.path:
    sys.path.insert(0, str(_BLENDER_SIM))

from disease_output_folder import disease_output_folder  # noqa: E402

_RE_DOUBLE = re.compile(r"^tangerine\d+__(.+)\.glb$", re.IGNORECASE)
_RE_SINGLE = re.compile(r"^tangerine\d+_(.+)\.glb$", re.IGNORECASE)


def _disease_from_name(name: str) -> str | None:
    m = _RE_DOUBLE.match(name)
    if m:
        return m.group(1)
    m = _RE_SINGLE.match(name)
    if m:
        return m.group(1)
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Move flat variant GLBs into disease subfolders")
    p.add_argument(
        "--dir",
        type=Path,
        default=ROOT / "data" / "Tangerine_3D" / "glb_procedural",
        help="변종 출력 루트 (기본: data/Tangerine_3D/glb_procedural)",
    )
    args = p.parse_args()
    base = args.dir.resolve()
    if not base.is_dir():
        print(f"[organize] 폴더 없음: {base}", file=sys.stderr)
        return 0

    moved = 0
    for f in sorted(base.iterdir()):
        if not f.is_file() or f.suffix.lower() != ".glb":
            continue
        if f.name.startswith("_"):
            continue
        dis = _disease_from_name(f.name)
        if not dis:
            print(f"[organize] 건너뜀 (이름 형식): {f.name}")
            continue
        sub = disease_output_folder(dis)
        dest_dir = base / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name
        if f.resolve() == dest.resolve():
            continue
        if dest.is_file():
            dest.unlink()
        f.rename(dest)
        print(f"[organize] {f.name} → {sub}/")
        moved += 1

    if moved:
        print(f"[organize] 완료: {moved}개 이동")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
