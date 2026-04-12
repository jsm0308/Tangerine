"""
`data/Fruits` 아래 JPG/ JPEG 원본을 읽어 rembg로 배경 제거 후 알파 기준 타이트 크롭한 PNG를
별도 출력 루트에 저장합니다. 원본은 삭제하지 않습니다.

사전 설치 (한 번):

  pip install "rembg[cpu]"

프로젝트 루트에서 실행:

  python scripts/remove_bg_crop_fruits.py

주요 옵션:

  --output-root PATH   기본: data/Fruits_nobg (클래스별 하위 폴더 구조 유지)
  --model NAME         기본: isnet-general-use (u2net 보다 일반 사물에 유리한 경우가 많음)
  --post-process-mask  rembg 마스크 후처리 (기본: 켜짐)
  --alpha-matting      경계 품질 개선 (느려질 수 있음)
  --include-png        입력에 PNG도 포함 (기본은 jpg/jpeg만)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 기본 입력은 JPG 계열만 (출력 PNG와 섞이지 않게)
JPG_EXT = {".jpg", ".jpeg"}
ALL_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _iter_images(root: Path, extensions: set[str]) -> list[Path]:
    out: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in extensions:
                out.append(p)
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fruits: rembg + bbox 크롭 → PNG (원본 유지)")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/Fruits"),
        help="입력 이미지 루트 (기본: data/Fruits)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/Fruits_nobg"),
        help="출력 PNG 루트 (클래스 폴더 구조 복제)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="isnet-general-use",
        help="rembg 세션 모델 이름 (예: u2net, isnet-general-use)",
    )
    parser.add_argument(
        "--post-process-mask",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="rembg 마스크 후처리 (기본: 켜짐)",
    )
    parser.add_argument(
        "--alpha-matting",
        action="store_true",
        help="알파 매팅 (경계 개선, 처리 시간 증가)",
    )
    parser.add_argument(
        "--include-png",
        action="store_true",
        help="입력에 PNG 포함 (기본은 jpg/jpeg만 처리)",
    )
    parser.add_argument("--dry-run", action="store_true", help="처리할 파일만 출력")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"디렉터리가 없습니다: {root}", file=sys.stderr)
        return 1

    ext_set = ALL_IMAGE_EXT if args.include_png else JPG_EXT
    paths = _iter_images(root, ext_set)
    if not paths:
        print(f"이미지가 없습니다: {root} (확장자 {ext_set})")
        return 0

    if args.dry_run:
        for p in paths:
            print(p.relative_to(project_root))
        return 0

    try:
        from rembg import new_session, remove
        from PIL import Image
    except ImportError as e:
        print('필요 패키지: pip install "rembg[cpu]" pillow', file=sys.stderr)
        raise SystemExit(1) from e

    session = new_session(args.model)

    ok = 0
    err = 0
    out_root = args.output_root.resolve()

    for input_path in paths:
        try:
            rel_under = input_path.relative_to(root)
        except ValueError:
            print(f"입력이 root 밖에 있습니다: {input_path}", file=sys.stderr)
            err += 1
            continue

        stem = input_path.stem
        out_path = out_root / rel_under.parent / f"{stem}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rel = input_path.relative_to(project_root)

        try:
            inp_img = Image.open(input_path)
            out_img = remove(
                inp_img,
                session=session,
                alpha_matting=args.alpha_matting,
                post_process_mask=args.post_process_mask,
            )
            bbox = out_img.getbbox()
            if bbox:
                out_img = out_img.crop(bbox)
            out_img.save(out_path)
            print(f"OK: {rel} -> {out_path.relative_to(project_root)}")
            ok += 1
        except Exception as e:
            print(f"FAIL: {rel}: {e}", file=sys.stderr)
            err += 1

    print(f"완료: 성공 {ok}, 실패 {err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
