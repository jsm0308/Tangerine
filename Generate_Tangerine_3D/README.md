# Generate_Tangerine_3D — 3D 귤 에셋 생성 (2트랙)

프로젝트 루트 기준 상대 경로입니다.

## 트랙 구분

| 트랙 | 폴더 | 설명 | 최종 GLB 저장 위치 |
|------|------|------|---------------------|
| **1 — 절차 셰이더 / YAML·설정** | [`procedural_track/`](procedural_track/) | `disease_overlays` + `variants_batch.yaml` 등 **코드·수치로 병해 재질**을 입히고 GLB로 베이크 | [`data/Tangerine_3D/glb_procedural/`](../data/Tangerine_3D/glb_procedural/) |
| **2 — 2D → 3D** | [`from_2d_track/`](from_2d_track/) | 병변 **마스크·패치 → UV 텍스처 스프레이** (기본) 또는 레거시 BOX 투영 — [`scripts/build_glb_from_2d.py`](../scripts/build_glb_from_2d.py) | [`data/Tangerine_3D/glb_from_2d/`](../data/Tangerine_3D/glb_from_2d/) |

`data/Tangerine_3D/` 아래에는 **위 두 종류의 최종 `.glb`만** 두고, 빌드용 설정·베이스 메시·중간 산출물은 이 `Generate_Tangerine_3D` 트리에 둡니다.

## 빠른 실행 (트랙 2)

1. `data/Fruits/` 에 클래스 폴더·이미지 준비.
2. `python scripts/build_glb_from_2d.py`  
   (설정: `from_2d_track/configs/from_2d_batch.yaml`)
3. 산출: `data/Tangerine_3D/glb_from_2d/`

## 빠른 실행 (트랙 1)

1. 베이스 메시 `tangerine0.glb` ~ `tangerine2.glb` 를 [`procedural_track/mesh_bases/`](procedural_track/mesh_bases/) 에 두거나, `build_base_mesh.py` 로 같은 폴더에 생성.
2. `python scripts/generate_variants_build.py`  
   (기본 설정: `Generate_Tangerine_3D/procedural_track/configs/variants_batch.yaml`)
3. 산출: `data/Tangerine_3D/glb_procedural/<healthy|Black spot|Canker|Greening|Scab>/tangerine*__.glb` (루트에 남은 파일은 `python scripts/organize_flat_variant_glbs.py`)

**건강 귤만 (3^5=243개: 크기·색·높이·형태 변주 포함, 긴 파일명):** `configs/variants_batch_healthy.yaml` 로 **`--no-clean` 필수**(다른 클래스 산출 유지). [docs/3D_GENERATION_NOTES.md](../docs/3D_GENERATION_NOTES.md) 참고.

참고 알베도 PNG: `python scripts/gen_disease_texture_masks.py` → `procedural_track/textures/disease/`.
