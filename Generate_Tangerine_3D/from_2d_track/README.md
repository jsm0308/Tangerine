# 트랙 2 — 2D 이미지 → 3D GLB (UV 텍스처 스프레이)

기본은 **`data/Tangerine_2D/`** (ImageFolder: 클래스별 하위 폴더·이미지). 다른 루트는 `from_2d_batch.yaml` 의 `fruits_root` 로 지정.

### Healthy 먼저 (권장 순서)

1. **베이스 메쉬**는 이미 healthy용 `tangerine_0~2.glb` (`mesh_paths`, 기본 `data/Tangerine_3D/` 루트).
2. **2D 데이터**도 우선 healthy(또는 `Normal` 등) 클래스 폴더만 넣고 `total_exports` 만 조정해 돌리면, 산출 `glb_from_2d/<그_클래스명>/` 에만 쌓인다 (`total_exports` 는 **클래스 수로 균등 분배**이므로 폴더가 1개면 전부 그 클래스).
3. 병해 클래스는 healthy 파이프라인이 안정된 뒤 같은 스크립트로 확장하면 된다.

### Seraph로 생성 (로컬 CPU 대신 GPU 서버)

로컬에서 `build_glb_from_2d.py` 를 직접 돌리면 전처리·Blender가 **이 PC CPU**에 걸린다. **Seraph(SSH)** 에서 같은 레포를 두고 `seraph_build_glb_from_2d_remote.py` 로 실행하면, 원격에서 `conda activate` 후 **`CUDA_VISIBLE_DEVICES` 를 지정**해 두고 `build_glb_from_2d.py` 가 돌아가므로 **PyTorch(SAM 등)·GPU** 를 쓰기 쉽다. 데이터(`data/Tangerine_2D`, `data/Tangerine_3D/tangerine*.glb`)는 **rsync/WinSCP로 Seraph 쪽 레포와 맞춘 뒤** 돌린다. 산출 GLB는 Seraph의 `data/Tangerine_3D/glb_from_2d/` 에 생기며, 필요하면 내려받는다.

## 동작 요약 (기본)

1. **전처리 (CPython):** 병변 마스크 → RGBA 패치 + `manifest.json` (`decal.cache_dir`, 기본 `decal_cache/`).
   - `decal.sam_checkpoint` 가 있으면 **SAM** 자동 마스크 (선택 의존성, GPU 권장).
   - 비어 있으면 **rembg 전경 + 명도 휴리스틱** 병변 후보.
   - 경계: 알파 페더 + (선택) OpenCV `seamlessClone` (Poisson류 합성).
2. **Blender:** `mesh_paths` 의 **healthy 베이스 GLB** 알베도(있으면)를 리사이즈해 초기 텍스처로 쓰고, 같은 UV 위에 패치를 **스탬프**. 알베도가 없으면 새 UV + 단색 베이스. → `*_tpaint.glb`.

레거시(전역 BOX 투영 + 정점색)는 `decal.enabled: false` → `fruit_class_mesh_export.py`.

## 한 줄로 실행

```bash
python scripts/build_glb_from_2d.py
```

기본 설정: [`configs/from_2d_batch.yaml`](configs/from_2d_batch.yaml)  
기본 산출: `data/Tangerine_3D/glb_from_2d/`  
패치 캐시: `decal_cache/` (설정의 `decal.cache_dir`)

## 코드가 있는 위치

| 역할 | 경로 |
|------|------|
| 런처 | [`scripts/build_glb_from_2d.py`](../../scripts/build_glb_from_2d.py) |
| 마스크·패치 전처리 | [`src/decal_prep/mask_and_patch.py`](../../src/decal_prep/mask_and_patch.py) |
| Blender 진입 | [`src/blender_sim/entries/decal_mesh_entry.py`](../../src/blender_sim/entries/decal_mesh_entry.py) |
| UV 텍스처 스탬프 | [`src/blender_sim/decal_mesh_export.py`](../../src/blender_sim/decal_mesh_export.py) |
| 레거시 진입·로직 | [`fruit_class_mesh_entry.py`](../../src/blender_sim/entries/fruit_class_mesh_entry.py), [`fruit_class_mesh_export.py`](../../src/blender_sim/fruit_class_mesh_export.py) |

마지막 작업 job: [`last_job.json`](last_job.json)

## SAM (선택)

```bash
pip install -r requirements.txt -r requirements-decal.txt
```

체크포인트 경로를 `from_2d_batch.yaml` 의 `decal.sam_checkpoint` 에 지정.

## Seraph에서 돌리기 (로컬 CPU 부담 완화)

**가능하다.** 로컬 CPU로 `build_glb_from_2d.py` 를 돌리지 말고, SSH로 Seraph에서 실행한다 ([`scripts/seraph_build_glb_from_2d_remote.py`](../../scripts/seraph_build_glb_from_2d_remote.py)). 스크립트가 원격에서 `CUDA_VISIBLE_DEVICES` 를 잡아 PyTorch(SAM 등)·CUDA를 쓰기 쉽게 한다.

```bash
python scripts/seraph_build_glb_from_2d_remote.py --pull
# 연결만 디버그:  python scripts/seraph_build_glb_from_2d_remote.py --ssh-v --pull
# GPU 여러 대 중 특정 번호:  python scripts/seraph_build_glb_from_2d_remote.py --cuda-device 1
# Slurm/module 등:           --remote-pre 'module load cuda/12.1'  (또는 SERAPH_REMOTE_PRE_CMD)
```

접속 직후 원격에서 `host=… time=…` / `cwd=…` 가 한 줄이라도 나와야 정상이다. 아무 것도 없으면 SSH 인증·네트워크를 의심하고 `--ssh-v` 로 재시도한다.

**전제:** Seraph 레포에 `data/Tangerine_3D/tangerine_0~2.glb`(루트), `data/Tangerine_2D/` 가 맞춰져 있어야 한다. 산출은 Seraph의 `data/Tangerine_3D/glb_from_2d/` → 필요 시 WinSCP로 동기화.

환경 변수 `SERAPH_SSH_HOST`, `SERAPH_REPO_ROOT`. 변종 절차용 [`seraph_build_variants_remote.py`](../../scripts/seraph_build_variants_remote.py) 와 같은 SSH 패턴이다.

## 설정 키 (`from_2d_batch.yaml`)

- `fruits_root`, `mesh_paths` (적어도 1개는 **실제 존재하는 파일**; 없으면 실패 — `data/` 자동 폴백 없음), `output_dir`, `total_exports`, `resume`
- `decal.*`: `enabled`, `cache_dir`, `sam_checkpoint`, `stamps_per_asset`, `texture_resolution`, `stamp_uv_radius`, `use_healthy_albedo_base`, 마스크 면적·페더 등

## 트랙 1과의 차이

| 트랙 1 (`procedural_track`) | 트랙 2 (`from_2d_track`) |
|-----------------------------|---------------------------|
| 절차 셰이더 + YAML | **실사 2D** → 병변 패치 → **UV 알베도 스탬프** |
| `glb_procedural/` | `glb_from_2d/` |
