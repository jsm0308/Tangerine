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
│   ├── README.txt            # base_mesh / variants_batch / default 역할
│   ├── default_config.yaml   # 전역 파이프라인 + Blender 경로
│   ├── base_mesh.yaml        # 베이스 GLB (단일 프리미티브)
│   └── variants_batch.yaml   # 병해 변종 배치
├── CONFIG_KEYS.md          # 설정 키 참조표
├── requirements.txt
├── README.md                 # 이 파일
├── docs/
│   └── PIPELINE.md           # 전체 파이프라인 상세 (데이터 흐름·Blender 분기·산출물)
├── assets/
│   └── README.txt            # GLB·텍스처 배치 안내
├── scripts/
│   ├── healthy_variants_build.py # 81종 형태 GLB + healthy 텍스처 배치
│   ├── build_base_mesh.py         # 베이스 GLB 3종 (configs/base_mesh.yaml)
│   ├── generate_variants_build.py # 병해 변종 GLB (configs/variants_batch.yaml)
│   ├── fruit_class_mesh_build.py # 클래스별 GLB 배치 (data/Fruits/)
│   ├── run_conveyor_demo.py      # 롤러 컨베이어 + data/ GLB(또는 구) → MP4
│   ├── balance_fruits_by_class.py # 클래스별 장수 밸런싱(복제)
│   ├── remove_bg_crop_fruits.py   # rembg 배경 제거·크롭
│   ├── png_to_jpg_flatten_fruits.py
│   └── run_blender_headless.sh
├── src/
│   ├── blender_sim/          # Blender 전용 (bpy)
│   │   ├── blender_entry.py      # main.py --stage blender 진입점
│   │   ├── simulation.py         # 벨트·리지드바디·렌더·frame_metadata.jsonl
│   │   ├── conveyor_entry.py + conveyor_demo/  # 프로시저 롤러 컨베이어 데모
│   │   ├── healthy_variants_entry.py / healthy_variants_export.py
│   │   ├── export_base_mesh.py   # (Blender) base_mesh job → GLB
│   │   ├── generate_variants.py / disease_materials.py  # 변종 GLB (절차적 병해 재질)
│   │   └── metadata_schema.json
│   ├── augment_2d/
│   │   └── pipeline.py       # 모션 블러·가우시안·JPEG
│   ├── inference/
│   │   └── pipeline.py       # YOLO detect + track + (선택) classify
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

### 컨베이어 데모 (`scripts/run_conveyor_demo.py`)

- **시나리오·물리·렌더** 기본값: `src/blender_sim/conveyor_demo/defaults.py` — 생성되는 `outputs/.../conveyor_demo.json`으로도 덮어쓸 수 있음.  
- **영상(MP4) + `.blend` 둘 다** — 기본 실행이 PNG→MP4이며, 씬 파일도 남기려면:

  `python scripts/run_conveyor_demo.py --also-blend`

- **영상 없이 `.blend`만(빠른 물리 확인)** — `python scripts/run_conveyor_demo.py --preview-blend --no-video`

- **GPU 렌더(Cycles)** — 기본이 GPU(`cycles_compute_device`). 드라이버/장치가 없으면 자동으로 CPU로 떨어질 수 있음.  
- **GLB는 종류당 1회만 임포트** 후 인스턴스 복제(`use_glb_instance_cache`) — 프레임마다 glTF 다시 읽지 않음.  
- **Seraph(Aurora)** — SSH **별칭 복붙**: `local/ssh_config_snippet_aurora_seraph.txt` → `~/.ssh/config` 에 붙이기. 비밀번호만: `local/aurora_seraph_credentials.txt` (Git 무시). **원격에서 GLB·컨베이어까지**: [docs/SERAPH_REMOTE_GUIDE.md](docs/SERAPH_REMOTE_GUIDE.md).

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
- 키 설명: [CONFIG_KEYS.md](CONFIG_KEYS.md)  
- 클래스 이름 `inference.class_names` 는 분류기 출력 차원·Blender GT 클래스와 **순서·이름을 맞출 것**.

---

## 관련 문서

- **[docs/PIPELINE.md](docs/PIPELINE.md)** — **0~4단계 순서**로 메인 파이프라인 전체(명령·입력·출력), 메인 외 경로(컨베이어 데모·GLB 빌드·전처리), 라벨·XAI·향후 확장  
- **[docs/SERAPH_REMOTE_GUIDE.md](docs/SERAPH_REMOTE_GUIDE.md)** — Aurora Seraph SSH 별칭·Cursor Remote-SSH·서버에서 변종 GLB / 컨베이어 데모 실행 순서  
- [docs/future_extensions.txt](docs/future_extensions.txt) — 확장 후보 한 페이지 요약  
- [CONFIG_KEYS.md](CONFIG_KEYS.md) — 설정 키 전체 표  
- [assets/README.txt](assets/README.txt) — healthy GLB 빌드 경로

---

## 라이선스

프로젝트 루트 정책에 따릅니다. (미기재 시 저장소 관리자에게 확인.)
