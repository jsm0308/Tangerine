Place reference assets here if needed.

**클래스별 GLB 배치 (질병 근사 + 폴더 이미지 혼합)**

- 입력: `data/Fruits/<클래스명>/` 하위 이미지 + `docs/DISEASE_SYNTH_REFERENCE.md` 참고
- 실행: `python scripts/fruit_class_mesh_build.py --config configs/default_config.yaml` (기본 15개)
- 산출물: `outputs/{experiment_id}/fruit_class_batch/<클래스>/`

**81 형태 GLB (healthy 첫 이미지)**

- `python scripts/healthy_variants_build.py --config configs/default_config.yaml`

**베이스 GLB 3종 (아이코스피어 등 단일 메시, 꼭지 없음)**

- 설정: `configs/base_mesh.yaml`
- `python scripts/build_base_mesh.py` → 기본 `assets/glb/*.glb`

**병해 절차적 재질 변종 (405 GLB)**

- 선행: 위 베이스 GLB 존재
- 설정: `configs/variants_batch.yaml`
- `python scripts/generate_variants_build.py --dry-run` 후 `python scripts/generate_variants_build.py`
- 산출물: `outputs/_variant_glb/*.glb`, `manifest.json` (기본 `output_dir`)

벨트 시뮬: `main.py --stage blender`
