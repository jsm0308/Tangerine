#!/usr/bin/env python3
"""
Colab 또는 로컬에서 Colab_From2D 폴더 안에서 실행:
  cd Colab_From2D
  python run_decal_cache.py

역할: 귤(과일) 이미지 → rembg 전경 + SAM(또는 명도 휴리스틱) 병변 마스크 → RGBA 패치 PNG + manifest.json

【필수 사전 준비 — 어떤 파일을 어디에 두는지】
  1) 이미지 (직접 업로드)
     - 경로: uploads/Tangerine_2D/<클래스이름>/이미지파일
     - 예: uploads/Tangerine_2D/Black_spot/img001.jpg
     - 지원 확장자: .png .jpg .jpeg .webp .bmp .tif .tiff
     - 클래스마다 반드시 하위 폴더를 만든다 (ImageFolder 구조).

  2) SAM 체크포인트 (SAM 방식으로 돌릴 때)
     - 기본 경로: checkpoints/sam_vit_b_01ec64.pth
     - 없으면 자동으로 rembg + LAB 명도 휴리스틱 폴백만 사용 (품질은 SAM보다 낮을 수 있음).
     - ViT-B: https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth

  3) 설정 파일
     - 이 스크립트와 같은 폴더의 decal_colab.yaml (fruits_root, decal.* 수정 가능).

산출물:
  - output/decal_cache/<클래스명>/*.png  (병변 패치)
  - output/decal_cache/manifest.json
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr)
    raise SystemExit(1)

from mask_and_patch import build_decal_cache, load_decal_config_defaults


def _resolve(root: Path, p: str | Path) -> Path:
    pp = Path(p)
    return pp.resolve() if pp.is_absolute() else (root / pp).resolve()


def main() -> int:
    os.chdir(ROOT)

    cfg_path = ROOT / "decal_colab.yaml"
    if not cfg_path.is_file():
        print(f"설정 파일 없음: {cfg_path}", file=sys.stderr)
        return 1

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    decal_defaults = load_decal_config_defaults()
    decal_user = data.get("decal") or {}
    decal_cfg: dict = {**decal_defaults, **decal_user}

    fruits_root = _resolve(ROOT, data.get("fruits_root", "uploads/Tangerine_2D"))
    cache_dir = decal_cfg.get("cache_dir") or "output/decal_cache"
    cache_root = _resolve(ROOT, cache_dir)

    sam_ck = (decal_cfg.get("sam_checkpoint") or "").strip()
    if sam_ck:
        sp = Path(sam_ck)
        if not sp.is_absolute():
            sp = ROOT / sp
        decal_cfg["sam_checkpoint"] = str(sp.resolve())

    if not fruits_root.is_dir():
        print(
            f"이미지 루트가 없습니다: {fruits_root}\n"
            "  uploads/Tangerine_2D/<클래스폴더>/ 이미지 구조로 만든 뒤 다시 실행하세요.",
            file=sys.stderr,
        )
        return 1

    print(f"[Colab_From2D] fruits_root={fruits_root}", flush=True)
    print(f"[Colab_From2D] cache_root={cache_root}", flush=True)
    sk = decal_cfg.get("sam_checkpoint") or ""
    print(f"[Colab_From2D] sam_checkpoint={sk or '(없음 → 휴리스틱 폴백)'}", flush=True)

    result = build_decal_cache(fruits_root, cache_root, decal_cfg)
    print(f"[Colab_From2D] 완료: {result.manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
