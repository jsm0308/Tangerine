# Colab_From2D

Google Colab에서 **병변 패치 캐시**(`manifest.json` + RGBA 패치 PNG)만 생성할 때 쓰는 폴더입니다. 전체 레포의 `scripts/build_glb_from_2d.py`(Blender GLB)와 달리, 여기서는 **CPython 전처리만** 포함합니다.

- **노트북:** `Colab_From2D.ipynb` — Colab에 업로드하거나 Drive에서 열기
- **업로드 안내:** `UPLOAD_GUIDE.txt`
- **설정:** `decal_colab.yaml`
- **실행:** `python run_decal_cache.py` (작업 디렉터리는 이 폴더)

`mask_and_patch.py` 는 레포의 `src/decal_prep/mask_and_patch.py` 와 동기화하는 **복사본**입니다.

이미지는 **`uploads/Tangerine_2D/<클래스>/`** 에 직접 넣습니다 (ImageFolder 구조).
