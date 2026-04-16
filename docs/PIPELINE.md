# 파이프라인 전체 (순서대로)

이 문서는 **메인 실험 흐름**을 처음부터 끝까지 **한 번에 따라 읽을 수 있게** 번호를 매겼습니다.  
(선택) 전처리·별도 Blender 데모는 **메인과 섞이지 않도록** 뒤쪽에 모았습니다.

---

## 읽는 방법

1. 아래 **「메인 파이프라인 — 순서」**만 위에서 아래로 읽으면 전 과정이 끝납니다.  
2. 폴더·파일 이름은 기본값(`configs/default_config.yaml` 미수정) 기준입니다.  
3. 실험 루트는 항상 **`{base_output_dir}/{experiment_id}/`** (예: `outputs/Exp_001/`).

---

## 메인 파이프라인 — 순서

### 0단계: 설정 준비

| 항목 | 내용 |
|------|------|
| **하는 일** | 실험 ID, Blender 경로, 해상도, 클래스 목록 등을 고른다. |
| **읽는 파일** | `config.py`(기본값), `configs/default_config.yaml`(덮어쓰기), 필요 시 `CONFIG_KEYS.md` |
| **산출물** | 없음 (이후 단계에서 `blender_config.json` 등이 생성됨) |

---

### 1단계: Blender 렌더 (합성 이미지 + GT 메타)

| 항목 | 내용 |
|------|------|
| **명령** | `python main.py --stage blender --config configs/default_config.yaml` |
| **입력** | 위 설정, Blender 설치(`blender_executable` 또는 PATH) |
| **처리** | ① `dump_blender_job()` → `outputs/{id}/blender_config.json` 저장 ② `blender --background --python src/blender_sim/entries/blender_entry.py -- blender_config.json` ③ `simulation.py` 가 씬 구성(벨트·측벽·UV 구체 귤·카메라·라이트)·물리 시뮬·프레임별 렌더 |
| **출력 (폴더)** | `outputs/{id}/renders/` — `frame_0001.png` … |
| **출력 (메타)** | `outputs/{id}/frame_metadata.jsonl` — 프레임·객체·`gt_disease_class`·`bbox_xyxy` 등 (한 줄 = 한 객체·한 프레임) |
| **비고** | 렌더 시 모션 블러는 끔 → 블러는 **2단계 augment**에서 줌. 귤 재질은 현재 클래스별 색(디버그); `texture_pools` 는 향후 텍스처 연결용 필드. |

**이 단계가 끝나야** 아래 2~4단계가 의미 있습니다.

---

### 2단계: 2D 증강

| 항목 | 내용 |
|------|------|
| **명령** | `python main.py --stage augment --config configs/default_config.yaml` |
| **입력** | `outputs/{id}/renders/*.png` (기본 `augment.input_subdir` = `renders`) |
| **처리** | `src/augment/pipeline.py` — `augment_order` 순서(기본: 모션 블러 → 가우시안 노이즈 → JPEG) |
| **출력** | `outputs/{id}/renders_aug/` — 파일명 동일, PNG 덮어쓰기 형태로 증강본 저장 (기본 `augment.output_subdir` = `renders_aug`) |

---

### 3단계: 검출 + 다중 객체 추적(MOT) + (선택) 질병 분류

| 항목 | 내용 |
|------|------|
| **명령** | `python main.py --stage infer --config configs/default_config.yaml` |
| **입력** | `outputs/{id}/renders_aug/` (기본 `inference.inference_input_subdir`) |
| **처리** | `src/inference/pipeline.py` — YOLO **detect** + **track**(예: ByteTrack, `persist=True`) → 박스·`track_id` → 크롭 리사이즈 → **선택** YOLO **classify** 로 질병 softmax. 분류 가중치가 없으면 균일 확률 + 경고 로그. |
| **출력** | `outputs/{id}/predictions.jsonl` — 프레임마다 한 줄 JSON: `frame_index`, `image`, `objects[]` (`track_id`, `bbox_xyxy`, `disease_probs`, `top_disease`, `alert` 등) |
| **비고** | `inference.class_names` 와 분류기 출력 차원·순서를 맞출 것. 검출 모델은 감귤 전용으로 학습한 가중치를 쓰는 것이 좋음(기본 `yolov8n.pt` 는 COCO). |

---

### 4단계: 리포트

| 항목 | 내용 |
|------|------|
| **명령** | `python main.py --stage report --config configs/default_config.yaml` |
| **입력** | `predictions.jsonl`, `frame_metadata.jsonl`, 증강 이미지 폴더(`renders_aug`) |
| **처리** | `src/reporting/generate.py` — GT bbox 와 예측 IoU 매칭, 정확도 요약, 크롭 저장, `report.md`, (옵션) HTML·차트 |
| **출력** | `outputs/{id}/reports/` — `report.md`, `report.html`, `predictions_table.csv`, `crops/`, `figures/` 등 |

---

### 한 번에 돌리기 (`--stage all`)

| 항목 | 내용 |
|------|------|
| **명령** | `python main.py --stage all --config configs/default_config.yaml` |
| **포함** | **2단계 augment → 3단계 infer → 4단계 report** 만 순서대로 실행 |
| **포함 안 됨** | **1단계 Blender** — 렌더가 이미 있어야 함. 처음이면 **먼저 `--stage blender`** 실행 |

---

## 메인 흐름 도식 (복습용)

```
[0 설정]
    ↓
[1 blender]  renders/*.png  +  frame_metadata.jsonl
    ↓
[2 augment]  renders_aug/*.png
    ↓
[3 infer]    predictions.jsonl
    ↓
[4 report]   reports/
```

---

## 메인이 아닌 경로 (같은 레포, 역할 다름)

아래는 **`main.py` 한 줄로 이어지지 않습니다.** 용도만 구분해서 사용합니다.

| 순서 | 이름 | 진입 | 나오는 것 | 비고 |
|------|------|------|-----------|------|
| A0 | 컨베이어 벨트 GLB (정적) | `python Conveyor_Lab/scripts/export_conveyor_glb.py` | `.glb` + 설정 JSON | [Conveyor_Lab/docs/CONVEYOR.md](../Conveyor_Lab/docs/CONVEYOR.md) §3 |
| A | 롤러 컨베이어 데모 (MP4) | `python Conveyor_Lab/scripts/run_conveyor_demo.py` | `conveyor_run.mp4` 등 | 전부 [Conveyor_Lab/docs/CONVEYOR.md](../Conveyor_Lab/docs/CONVEYOR.md) |
| B | Healthy GLB 81종 빌드 | `python scripts/healthy_variants_build.py` | `outputs/.../healthy_variants_glb/*.glb` | **에셋 생성**; 학습용 프레임 메타와 직접 연결되지 않음 |
| B1 | 베이스 GLB 3종 | 작업자 에셋 `tangerine0/1/2.glb` → `Generate_Tangerine_3D/procedural_track/mesh_bases/` (선택: `build_base_mesh.py` 로 아이코스피어) | 동 경로 | 변종 전에 필수 |
| B1a | 병해 알베도 PNG (선택) | `python scripts/gen_disease_texture_masks.py` | `Generate_Tangerine_3D/procedural_track/textures/disease/*_albedo.png` | B2와 무관; 참고·2D 합성용 |
| B2 | healthy 틴트 + 병해 오버레이 → EMIT 베이크 → glTF | `python scripts/generate_variants_build.py` (`Generate_Tangerine_3D/procedural_track/configs/variants_batch.yaml`) | `data/Tangerine_3D/glb_procedural/*.glb` + `manifest.json` | B1 이후; [DISEASE_MATERIALS.md](DISEASE_MATERIALS.md) (클래스별 스펙); 기본 **15**개(베이스 3×병해 5; YAML에서 형태·색 그리드 확장 가능) |
| C | 원천 이미지 전처리 | `scripts/remove_bg_crop_fruits.py`, `balance_fruits_by_class.py` 등 | `data/` 쪽 폴더 | **학습 데이터 준비**용; 파이프라인 필수 단계 아님 |

**학습·리포트 GT 정본**은 **`simulation.py` 줄기(1단계)** 로 두는 것을 권장합니다.

---

## 데이터·라벨 (한 번만 짚기)

- 합성 GT: **`frame_metadata.jsonl`** 의 `gt_disease_class` (객체 단위).  
- 실제 분류 학습 시 **폴더명 = 클래스** 도 병행 가능 — 본 레포 합성 경로와 별개로 이해하면 됨.  
- 픽셀 단위 병변 마스크는 **현재 스키마 필수 아님** — 세그·정밀 XAI 를 나중에 넣을 때 확장.

---

## 해석 가능성(XAI)

- 본 레포 **추론 코드**에는 Grad-CAM 저장이 없음.  
- 권장: 학습된 분류기에 대해 **추론 후** 별도 스크립트로 히트맵 생성 → `reports/figures/` 에 넣어 `report.md` 에 링크.

---

## 향후 확장 (필수 아님)

자세한 한 줄 목록: **`docs/future_extensions.txt`**

요약:

- 도메인 적응, Diffusion 인페인팅, 2단계 세그, 지식 증류·LoRA, ONNX/TensorRT 등  
- **롤러·벨트에 디테일한 물리 법칙 적용** (마찰·굴림·구동 토크·접촉 모델 등) — 현재는 Blender 리지드 바디 + 키프레임 수준; `blender_sim/conveyor/` 의 롤러 회전·마찰 계수 등을 확장할 때 검토

---

## 의존성·문제 시

- **의존성**: `requirements.txt` + PyTorch(별도 설치).  
- **`--stage all` 실패**: `renders/` 가 있는지, `inference.inference_input_subdir` 가 증강 출력 폴더와 같은지 확인.  
- **Blender 못 찾음**: `configs/default_config.yaml` 의 `blender_executable` 또는 PATH.

---

## 참고 파일

| 파일 | 용도 |
|------|------|
| `config.py` | 모든 설정 기본값 |
| `CONFIG_KEYS.md` | 키 표 |
| `src/blender_sim/metadata_schema.json` | JSONL 필드 설명 |

코드 변경 시 이 문서를 함께 고치는 것을 권장합니다.
