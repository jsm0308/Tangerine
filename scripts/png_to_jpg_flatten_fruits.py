"""
현재 data/Fruits 아래 PNG(RGBA)를 흰 배경 RGB JPG로 바꿉니다. 이전에 삭제된 원본 JPG는
복구할 수 없으므로, 투명 영역은 흰색으로 채워집니다.

프로젝트 루트에서:

  python scripts/png_to_jpg_flatten_fruits.py

옵션:

  --root PATH      기본: data/Fruits
  --quality N      JPEG 품질 1–95 (기본 95)
  --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fruits PNG → 흰 배경 JPG, PNG 삭제")
    parser.add_argument("--root", type=Path, default=Path("data/Fruits"))
    parser.add_argument("--quality", type=int, default=95, help="JPEG 품질 (1–95)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"디렉터리가 없습니다: {root}", file=sys.stderr)
        return 1

    q = max(1, min(95, args.quality))

    try:
        from PIL import Image
    except ImportError as e:
        print("pip install pillow", file=sys.stderr)
        raise SystemExit(1) from e

    pngs = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".png"]

    if not pngs:
        print(f"PNG가 없습니다: {root}")
        return 0

    if args.dry_run:
        for p in sorted(pngs):
            print(p.relative_to(project_root))
        return 0

    ok = 0
    err = 0
    for png_path in sorted(pngs):
        jpg_path = png_path.with_suffix(".jpg")
        rel = png_path.relative_to(project_root)
        try:
            im = Image.open(png_path).convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            bg.save(jpg_path, quality=q, optimize=True)
            png_path.unlink()
            print(f"OK: {rel} → {jpg_path.name}")
            ok += 1
        except Exception as e:
            print(f"FAIL: {rel}: {e}", file=sys.stderr)
            err += 1

    print(f"완료: 성공 {ok}, 실패 {err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
