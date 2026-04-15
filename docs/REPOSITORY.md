# 레포지토리 구조 (핵심만)

Tangerine은 **Blender 합성(물리·렌더)** 과 **Python 후단(증강·검출·리포트)** 이 한 레포에 들어 있다. 아래는 **처음 열 때 볼 폴더·파일** 위주로 정리했다.

---

## 루트 — 진입점과 설정


| 항목                            | 설명                                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| `main.py`                     | CLI: `blender`, `augment`, `infer`, `postprocess`, `report`, `all`, `vision_all`. 설정은 `--config` YAML. |
| `config.py`                   | `PipelineConfig` dataclass, 기본값과 YAML 병합.                                                              |
| `configs/default_config.yaml` | 전역 파이프라인·Blender 경로·추론 클래스 등.                                                                          |
| `data/Tangerine_3D/configs/variants_batch.yaml` | 병해 변종 GLB 배치·베이크 해상도 등 (`DISEASE_MATERIALS.md`와 짝). |
| `data/Tangerine_3D/configs/base_mesh.yaml`      | (선택) 아이코스피어 베이스 빌드.                                   |
| `CONFIG_KEYS.md`              | YAML 키 빠른 참조.                                                                                          |


---

## `src/` — 코드의 중심

### `src/blender_sim/` (Blender + `bpy` 전용)


| 경로                                                                                                                     | 역할                                                                             |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `entries/`                                                                                                             | `blender --background --python` 으로만 돌리는 **진입 스크립트** (메인 시뮬, 컨베이어, GLB 익스포트 등). |
| `conveyor/`                                                                                                            | 롤러 컨베이어 데모: 물리·스폰·렌더 (`Conveyor_Lab/scripts/run_conveyor_demo.py`가 호출).                             |
| `simulation.py`                                                                                                        | `main.py --stage blender` 가 쓰는 **기본 벨트 시뮬**·렌더·`frame_metadata.jsonl`.         |
| `generate_variants.py`, `disease_materials.py`, `disease_overlays.py`, `material_preserve.py`, `gltf_material_bake.py` | 병해 변종 GLB 파이프라인.                                                               |
| `healthy_variants_export.py`, `fruit_class_mesh_export.py`, `export_base_mesh.py`                                      | 형태·클래스별 GLB 등 보조 빌드.                                                           |
| `metadata_schema.json`                                                                                                 | `frame_metadata.jsonl` 필드 설명.                                                  |


### `src/augment/`

렌더 PNG에 **2D 증강** (모션 블러·가우시안·JPEG 등). `config`의 `augment_order` 순서를 따른다.

### `src/inference/`


| 경로                                                                            | 역할                                                      |
| ----------------------------------------------------------------------------- | ------------------------------------------------------- |
| `pipeline.py`                                                                 | 추론 단계 진입.                                               |
| `backends.py`                                                                 | YOLO 계열 / Mask R-CNN 등 **검출 백엔드 분기**.                   |
| `yolo_runner.py`, `mask_rcnn_runner.py`, `classifiers.py`, `iou_tracker.py` 등 | 실제 모델·트래킹 로직.                                           |
| `preprocess/`                                                                 | YAML 키 이름은 그대로 `preprocess` — 벨트 **슬롯·트리거** (프레임 동기 등). |


### `src/postprocess/`

추론 결과를 **논리 큐·구동 신호** 쪽으로 넘기는 단계 (설정에 따라 JSONL/출력).

### `src/reporting/`

크롭·CSV·Markdown/HTML 리포트 (`templates/report.html.j2`).

---

## `scripts/` — 사람이 직접 자주 켜는 것


| 스크립트                                                                           | 용도                                    |
| ------------------------------------------------------------------------------ | ------------------------------------- |
| `run_conveyor_demo.py`                                                         | 컨베이어 MP4·(옵션) `.blend` — 구현은 `Conveyor_Lab/scripts/`. |
| `generate_variants_build.py`                                                   | 병해 변종 GLB 일괄 (`data/Tangerine_3D/configs/variants_batch.yaml`). |
| `healthy_variants_build.py`, `build_base_mesh.py`, `fruit_class_mesh_build.py` | 형태·베이스·클래스별 GLB.                      |
| `export_conveyor_glb.py`                                                       | 컨베이어 벨트 메시만 GLB — 구현은 `Conveyor_Lab/scripts/`. |
| `gen_disease_texture_masks.py`                                                 | 2D 알베도/마스크 생성 (변종 절차 재질과는 별 트랙 가능).   |
| `seraph_build_variant_glb.sh`, `seraph_build_variants_remote.py`               | 원격 Seraph에서 변종 빌드 (`docs/SERAPH.md`). |
| 그 외 `balance_`*, `remove_bg_*`, `png_to_jpg_*`                                 | 데이터 전처리·정리 유틸.                        |


---

## `docs/` — 무엇을 읽을지


| 문서                                           | 내용                          |
| -------------------------------------------- | --------------------------- |
| [INDEX.md](INDEX.md)                         | 문서 목록.                      |
| [PIPELINE.md](PIPELINE.md)                   | 메인 0~4단계·데이터가 어디로 흐르는지.     |
| [REPOSITORY.md](REPOSITORY.md)               | 이 파일 — 폴더 역할 요약.            |
| [DISEASE_MATERIALS.md](DISEASE_MATERIALS.md) | 병해 클래스별 절차 재질 스펙·품질 팁. |
| [Conveyor_Lab/docs/CONVEYOR.md](../Conveyor_Lab/docs/CONVEYOR.md) | 컨베이어 실행·산출물 (`CONVEYOR_DEMO.md`는 리다이렉트). |
| [SERAPH.md](SERAPH.md)                       | Seraph 서버·Git·Blender 한 문서. |


---

## 그 외 디렉터리


| 경로         | 설명                                                   |
| ---------- | ---------------------------------------------------- |
| `Conveyor_Lab/` | 롤러 컨베이어 실험: `scripts/`·`docs/CONVEYOR.md`·기본 산출 `outputs/`. |
| `assets/`  | GLB·텍스처 등 입력 에셋 (`README.txt` 참고).                   |
| `outputs/` | 실험 산출물 기본 루트 (`base_output_dir` / `experiment_id`).  |
| `local/`   | SSH 스니펫·자격 증명 예시 (**Git에 올리지 않도록** `.gitignore` 확인). |


---

## 추천 읽기 순서 (신규 기여자)

1. 루트 `README.md` — 한 줄 파이프라인.
2. `docs/PIPELINE.md` — 단계별 입출력.
3. 담당 영역: 합성이면 `blender_sim/` + `DISEASE_MATERIALS.md` 또는 `Conveyor_Lab/docs/CONVEYOR.md`, 추론이면 `inference/` + `CONFIG_KEYS.md`.

