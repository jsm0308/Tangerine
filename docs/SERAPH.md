# Seraph(Aurora) — 한 문서로 보기

같은 GitHub 레포를 **로컬에서 편집**하고 **Seraph에서 무거운 Blender·렌더**를 돌리는 경우를 기준으로, 접속·환경·Git 동기화·실행·변종 GLB 빌드를 한곳에 모았다.

**다른 문서:** 컨베이어는 [Conveyor_Lab/docs/CONVEYOR.md](../Conveyor_Lab/docs/CONVEYOR.md) 한 곳, 메인 실험 흐름은 [PIPELINE.md](PIPELINE.md).

---

## 1. 로컬 PC vs Seraph — 무엇을 어디에 두나

| 항목 | 로컬 (Windows 등) | Seraph (`/data/minjae051213/...`) |
| --- | --- | --- |
| **레포 소스** | `git clone` / 작업 폴더 | `git clone` 동일 레포 (예: `Tangerine/`) |
| **Python** | 로컬 venv 또는 시스템 Python | **Conda** 환경 `tangerine` (`~/miniconda3/envs/tangerine`) |
| **비밀번호·SSH** | `local/aurora_seraph_credentials.txt` (**Git 무시**) | 해당 파일은 **올리지 않음** — 필요 시 로컬에서만 보관·복사 |
| **SSH 별칭 예시** | `local/ssh_config_snippet_aurora_seraph.txt` → `~/.ssh/config` | 접속 **대상** (서버 쪽에 별도 저장 불필요) |
| **대용량 학습 이미지** | `data/Fruits/` 등 (**Git에 포함 안 함**) | 필요하면 **직접 복사·rsync** (레포에 없음) |
| **Blender** | 설치 경로 또는 `BLENDER_EXECUTABLE` | `which blender` 또는 관리자 지정 경로 |
| **산출물 (실험 결과)** | `outputs/...` (로컬 실행 시) | `outputs/...` (**Seraph 디스크에 저장** — 컨베이어 MP4, `_variant_glb` 등) |
| **GLB 에셋 (생성됨)** | 로컬에서 빌드 시 `data/Tangerine_3D/`·`outputs/` | Seraph에서 빌드 시 **Seraph 경로에만** 생김 — 로컬과 자동 동기화 **안 됨** |

### 동기화 원칙

1. **코드·설정** → **Git** (`git push` / Seraph에서 `git pull`).
2. **생성된 GLB·영상·대용량 데이터** → Git에 넣지 않거나(`.gitignore`), 필요 시 **수동 복사·별도 스토리지**.
3. Seraph에서 만든 `Conveyor_Lab/outputs/conveyor_demo/conveyor_run.mp4` 등을 로컬로 가져오려면 **scp/rsync** 또는 Cursor로 파일 다운로드.

### 권장 작업 방식

- **한 번에 하나의 무거운 작업** (Blender GPU 렌더 2개 동시 실행은 GPU·큐 경합 가능).
- `fruit_kind` 가 `glb_citrus` 이면 해당 GLB가 Seraph 레포 경로에 있어야 한다 ([Conveyor_Lab/docs/CONVEYOR.md](../Conveyor_Lab/docs/CONVEYOR.md) §4). 기본 구 모드는 불필요.

---

## 2. 코드 올리기·내리기 (Git)

GitHub(`origin`)를 가운데 두고 **로컬 PC**와 **Seraph**가 같은 레포를 쓴다.

### 로컬에서 고친 코드 → Seraph에 반영

**로컬 (Windows, 프로젝트 폴더에서):**

```text
git add -A
git commit -m "메시지"
git push origin main
```

**Seraph (SSH 접속 후):**

```bash
cd /data/minjae051213/Tangerine
git pull origin main
```

### Seraph에서 고친 코드 → 로컬로 가져오기

**Seraph에서 커밋까지 한 경우:**

```bash
cd /data/minjae051213/Tangerine
git add -A
git commit -m "메시지"
git push origin main
```

**로컬에서:**

```text
git pull origin main
```

### Git 없이 파일만 복사 (선택)

- **로컬 → Seraph:** PowerShell 등에서 `scp -P 30080 -r 경로 minjae051213@aurora.khu.ac.kr:/data/minjae051213/Tangerine/`
- **Seraph → 로컬:** `scp -P 30080 minjae051213@aurora.khu.ac.kr:/data/.../파일 로컬경로`

(포트·호스트는 `local/ssh_config_snippet_aurora_seraph.txt` 와 동일.)

### 한 줄 요약

| 하고 싶은 것 | 할 일 |
| --- | --- |
| 로컬 수정 → Seraph | 로컬 `git push` → Seraph `git pull` |
| Seraph 수정 → 로컬 | Seraph `git push` → 로컬 `git pull` |
| 실행 | Seraph에서 `conda activate` → `cd Tangerine` → `python ...` |

---

## 3. SSH

- 별칭 복붙: 레포의 `local/ssh_config_snippet_aurora_seraph.txt` → Windows `%USERPROFILE%\.ssh\config`
- 비밀번호: `local/aurora_seraph_credentials.txt` (Git 무시, 로컬만)

```bash
ssh aurora-seraph
```

---

## 4. Cursor Remote-SSH

F1 → `Remote-SSH: Connect to Host...` → `aurora-seraph` → Open Folder: `/data/minjae051213` (또는 `.../Tangerine`)

---

## 5. 레포 클론 (Seraph)

```bash
cd /data/minjae051213
git clone https://github.com/jsm0308/Tangerine.git   # 본인 URL
cd Tangerine
git pull
```

---

## 6. Python (sudo 없을 때: Conda 권장)

`python3 -m venv` 가 실패하면 시스템에 `python3-venv` 가 없는 경우가 많음 → **홈에 Miniconda** 설치 후:

```bash
# 최초 1회: ToS 오류 시 안내에 따라
#   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
#   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda create -n tangerine python=3.10 -y
```

매 세션:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate tangerine
cd /data/minjae051213/Tangerine
pip install -r requirements.txt
```

환경 위치: `~/miniconda3/envs/tangerine`

---

## 7. Blender

```bash
which blender
blender --version
```

없으면 관리자에게 경로 문의. `Conveyor_Lab/scripts/run_conveyor_demo.py`(또는 루트 `scripts/run_conveyor_demo.py`)에 `--blender /전체/경로` 가능.

---

## 8. Seraph에서 코드 실행 (예: 컨베이어)

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate tangerine
cd /data/minjae051213/Tangerine
git pull
python Conveyor_Lab/scripts/run_conveyor_demo.py --out Conveyor_Lab/outputs/conveyor_demo --frames 240
```

`--blender /절대/경로/blender` — Blender가 PATH에 없을 때.  
CLI·산출물·기울기·과일 모드: **[Conveyor_Lab/docs/CONVEYOR.md](../Conveyor_Lab/docs/CONVEYOR.md)** (Seraph 전용 반복 설명은 두지 않음).

---

## 9. 변종 GLB 전체 빌드 (Seraph)

**Seraph에 이미 SSH·Conda·Blender·`git pull` 된 레포가 있다고 가정한다.**

### A) Seraph 셸에서 직접

```bash
cd /data/minjae051213/Tangerine
git pull   # 선택
chmod +x scripts/seraph_build_variant_glb.sh   # 최초 1회
./scripts/seraph_build_variant_glb.sh
```

또는:

```bash
bash scripts/seraph_build_variant_glb.sh
```

선택 환경 변수: `SERAPH_REPO_ROOT`, `SERAPH_GIT_PULL=1`(스크립트 안에서 pull).

### B) 로컬 PC에서 SSH로 원격 실행

```bash
python scripts/seraph_build_variants_remote.py
# 원격에서 pull 까지:
python scripts/seraph_build_variants_remote.py --pull
```

`--host aurora-seraph`, `--remote-root /data/.../Tangerine` 으로 바꿀 수 있다.

산출: Seraph 디스크의 `outputs/_variant_glb/*.glb` + `manifest.json` (로컬과 자동 동기화 안 됨 — 필요 시 scp/rsync).

### C) 한 단계만

- 알베도 PNG만: `python scripts/gen_disease_texture_masks.py`
- 베이스 GLB만: `python scripts/build_base_mesh.py`
- 변종만(텍스처·베이스 이미 있을 때): `python scripts/generate_variants_build.py`

Blender 경로는 `configs/default_config.yaml` 의 `blender_executable` 또는 Seraph `PATH` 의 `blender`.
