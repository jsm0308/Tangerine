# Tangerine — 합성 데이터·감귤 병해 추론 파이프라인

Blender로 **컨베이어·물리 시뮬**과 **렌더**를 만들고, Python으로 **2D 증강 → YOLO 검출·추적(MOT) → (선택) 분류 → 리포트**까지 한 실험 폴더에 모읍니다.

**도메인(조명·카메라·벨트·재질)** 은 우선 **Blender에서 다양화**하는 것을 기본으로 합니다. 실사–합성 갭을 줄이기 위한 고급 기법(도메인 적응, Diffusion 인페인팅 등)은 필수가 아니며, 필요 시 [docs/PIPELINE.md](docs/PIPELINE.md)의 *향후 확장*을 참고합니다.

---

## 요구 사항

- Python 3.10+ 권장  
- [PyTorch](https://pytorch.org/) (CUDA/CPU는 환경에 맞게)  
- `pip install -r requirements.txt`  
- **Blender** (헤드리스 렌더): `blender` / `blender.exe` 가 PATH에 있거나 `configs/default_config.yaml`의 `blender.blender_executable` 지정  
- (선택) `ffmpeg` — 컨베이어 데모 MP4 인코딩

---

## 레포지토리 구조

```
Tangerine/
├── main.py                 # CLI: blender | augment | infer | report | all
├── config.py               # PipelineConfig (dataclass), YAML 병합
├── configs/
│   ├── README.txt            # default_config 역할
│   └── default_config.yaml   # 전역 파이프라인 + Blender 경로
├── Generate_Tangerine_3D/   # 3D 생성 2트랙: procedural_track (설정·베이스 메시), from_2d_track (2D→3D)
├── Colab_From2D/            # Google Colab: 데칼 패치 캐시만 (이미지는 uploads/Tangerine_2D/에 업로드)
├── data/
│   └── Tangerine_3D/         # 최종 GLB만: glb_procedural / glb_from_2d
├── configs/CONFIG_KEYS.md  # 설정 키 참조표
├── requirements.txt
├── README.md                 # 이 파일
├── Conveyor_Lab/           # 롤러 컨베이어 실험: 스크립트·문서·기본 산출 (코드는 src/blender_sim/conveyor/)
├── docs/
│   ├── PIPELINE.md           # 전체 파이프라인 상세
│   ├── REPOSITORY.md         # 핵심 폴더·파일 안내
│   └── …                     # CONVEYOR_DEMO(리다이렉트), SERAPH, DISEASE_MATERIALS 등 (INDEX.md)
├── scripts/
│   ├── healthy_variants_build.py # 81종 형태 GLB + healthy 텍스처 배치
│   ├── build_base_mesh.py         # (선택) 아이코스피어 베이스 → procedural_track/mesh_bases
│   ├── generate_variants_build.py # 병해 변종 GLB → data/Tangerine_3D/glb_procedural
│   ├── variant_qc_pipeline.py     # 렌더 QC 루프(실패 시 disease_params 보정·재빌드)
│   ├── qc_preview_only.py        # 기존 GLB 미리보기 PNG + 수치 QC만
│   ├── fruit_class_mesh_build.py # 클래스별 GLB 배치 (data/Fruits/)
│   ├── run_conveyor_demo.py      # → Conveyor_Lab/scripts/ (호환)
│   ├── export_conveyor_glb.py    # → Conveyor_Lab/scripts/ (호환)
│   ├── balance_fruits_by_class.py # 클래스별 장수 밸런싱(복제)
│   ├── remove_bg_crop_fruits.py   # rembg 배경 제거·크롭
│   ├── png_to_jpg_flatten_fruits.py
│   └── run_blender_headless.sh
├── src/
│   ├── blender_sim/          # Blender 전용 (bpy)
│   │   ├── entries/              # `blender --python` 진입 스크립트만 모음
│   │   ├── conveyor/             # 롤러 컨베이어 데모 (물리·스폰·렌더)
│   │   ├── simulation.py         # 메인 시뮬 벨트·렌더·frame_metadata.jsonl
│   │   ├── healthy_variants_export.py / fruit_class_mesh_export.py
│   │   ├── export_base_mesh.py   # (Blender) base_mesh job → GLB
│   │   ├── generate_variants.py / disease_materials.py
│   │   └── metadata_schema.json
│   ├── augment/
│   │   └── pipeline.py       # 렌더 PNG 2D 증강 (모션 블러·가우시안·JPEG)
│   ├── inference/
│   │   ├── pipeline.py / backends.py  # 검출 백엔드 분기
│   │   └── preprocess/      # 벨트 슬롯·트리거 (YAML 키는 여전히 `preprocess`)
│   └── reporting/
│       ├── generate.py       # report.md, HTML, crops, CSV
│       └── templates/report.html.j2
└── outputs/                  # 실험 산출물 (기본: outputs/{experiment_id}/)
```

---

## 한 줄 파이프라인

1. **Blender** — 장면 생성·물리·PNG 시퀀스 + `frame_metadata.jsonl` (GT 클래스·2D bbox 등)  
2. **augment** — 렌더 PNG에 2D 증강 → `renders_aug/`  
3. **infer** — YOLO **검출 + 다중 객체 추적(MOT)** + 크롭별 **(선택) 질병 분류** → `predictions.jsonl`  
4. **report** — 크롭·표·요약 MD/HTML

`--stage all` 은 **augment → infer → report** 만 실행합니다. **Blender는 별도로** `--stage blender` 를 먼저 돌리거나, 이미 `renders/` 가 있어야 합니다.

---

## 빠른 실행

```bash
# 1) 합성 렌더 + 메타데이터
python main.py --stage blender --config configs/default_config.yaml

# 2) 증강 → 추론 → 리포트
python main.py --stage all --config configs/default_config.yaml
```

개별 단계: `augment`, `infer`, `report`.

### 컨베이어 데모 (`Conveyor_Lab/`)

- **한 문서로 정리**: [Conveyor_Lab/docs/CONVEYOR.md](Conveyor_Lab/docs/CONVEYOR.md) — 루트 `scripts/run_conveyor_demo.py` 는 동일 스크립트로 연결  
- **Seraph·Git·SSH**: [docs/SERAPH.md](docs/SERAPH.md) — 컨베이어·원격 빌드 요약; 트랙별 세부는 [Generate_Tangerine_3D/from_2d_track/README.md](Generate_Tangerine_3D/from_2d_track/README.md)

---

## 설계 방향 (요약)

| 영역 | 선택 |
|------|------|
| 객체 위치·추적 | **YOLO 검출 + 트래커**(예: ByteTrack). 귤 박스는 이 경로에서 담당. |
| 질병 판정 | 크롭 단 **분류기**(Ultralytics `classify`, 가중치 있을 때). 없으면 균일 확률로 파이프라인만 통과. |
| 도메인 | **Blender**에서 조명·카메라·물리·(설정에 따른) 텍스처 풀. 후단 **OpenCV 증강**. |
| 해석 가능성(XAI) | 학습된 분류/세그 모델에 **Grad-CAM 등 사후 시각화**를 붙이는 형태를 권장. 본 레포 추론 단계에는 아직 미포함 — [docs/PIPELINE.md](docs/PIPELINE.md) 참고. |
| 실제 공장 이미지 부족 | 합성 + 필요 시 소량 실사·폴더(클래스) 라벨. 고급 도메인 적응은 선택 사항. |

---

## 설정

- 전역: `config.py` + `configs/default_config.yaml`  
- 키 설명: [configs/CONFIG_KEYS.md](configs/CONFIG_KEYS.md)  
- 클래스 이름 `inference.class_names` 는 분류기 출력 차원·Blender GT 클래스와 **순서·이름을 맞출 것**.

---

## 관련 문서

- **[docs/INDEX.md](docs/INDEX.md)** — 문서 색인 (여기서부터)  
- **[docs/REPOSITORY.md](docs/REPOSITORY.md)** — **핵심 폴더·파일** 한눈 요약  
- **[docs/PIPELINE.md](docs/PIPELINE.md)** — 메인 0~4단계, 부가 경로(B·컨베이어) 표  
- **[docs/3D_GENERATION_NOTES.md](docs/3D_GENERATION_NOTES.md)** — 절차 3D 변종 GLB: **현재 방식·시도 기록**(프로토타입 반복용)  
- **[Conveyor_Lab/docs/CONVEYOR.md](Conveyor_Lab/docs/CONVEYOR.md)** — 컨베이어 데모 전용 (실행·산출·설정)  
- **[docs/SERAPH.md](docs/SERAPH.md)** — **Seraph 한 문서:** 로컬 vs 서버, Git, SSH·Conda·Blender, 실행, 변종 GLB  
- [docs/future_extensions.txt](docs/future_extensions.txt) — 확장 후보  
- [configs/CONFIG_KEYS.md](configs/CONFIG_KEYS.md) — 설정 키 표

---

## 라이선스

프로젝트 루트 정책에 따릅니다. (미기재 시 저장소 관리자에게 확인.)
