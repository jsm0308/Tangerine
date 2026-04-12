"""
클래스(하위 폴더)별 이미지 수를 **가장 많은 클래스 장수**에 맞춥니다.
부족한 클래스는 같은 클래스 안에서 **복제(랜덤 복원 추출)** 로 채웁니다.

프로젝트 루트에서:

  python scripts/balance_fruits_by_class.py --input data/Fruits --output data/Fruits_balanced

원본은 건드리지 않고 `--output` 에만 복사·추가합니다.
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _list_images(folder: Path) -> list[Path]:
    out: list[Path] = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXT:
            out.append(p)
    return sorted(out)


def balance_class_folders(
    input_root: Path,
    output_root: Path,
    seed: int,
) -> dict[str, int]:
    """
    `input_root` 의 직계 하위 폴더를 클래스로 보고, 각 폴더 안 이미지 수를 max 에 맞춥니다.
    반환: { 클래스명: 최종 장수 }
    """
    random.seed(seed)
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    class_dirs = sorted([d for d in input_root.iterdir() if d.is_dir()])
    if not class_dirs:
        raise SystemExit(f"하위 클래스 폴더가 없습니다: {input_root}")

    counts: dict[str, list[Path]] = {}
    for d in class_dirs:
        imgs = _list_images(d)
        counts[d.name] = imgs

    target = max(len(v) for v in counts.values())
    print(f"[balance] 클래스당 목표 장수(최다 클래스 기준): {target}")

    summary: dict[str, int] = {}
    for name, imgs in counts.items():
        out_dir = output_root / name
        out_dir.mkdir(parents=True, exist_ok=True)
        # 원본 전부 복사
        for src in imgs:
            shutil.copy2(src, out_dir / src.name)
        n = len(imgs)
        need = target - n
        dup_idx = 0
        while need > 0:
            src = random.choice(imgs)
            stem = src.stem
            ext = src.suffix
            while True:
                dup_idx += 1
                dest = out_dir / f"{stem}__bal{dup_idx:04d}{ext}"
                if not dest.exists():
                    break
            shutil.copy2(src, dest)
            need -= 1
        final_n = len(_list_images(out_dir))
        summary[name] = final_n
        print(f"  {name}: {len(imgs)} → {final_n}")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="클래스별 이미지 수를 최다 클래스에 맞춤")
    parser.add_argument("--input", type=Path, default=Path("data/Fruits"), help="클래스별 하위 폴더가 있는 루트")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/Fruits_balanced"),
        help="균형 맞춘 복사본을 둘 경로 (원본과 분리)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)

    inp = args.input.resolve()
    if not inp.is_dir():
        print(f"입력 폴더가 없습니다: {inp}", file=sys.stderr)
        return 1

    balance_class_folders(inp, args.output, args.seed)
    print(f"[balance] 완료 → {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
