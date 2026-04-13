# Seraph(Aurora) — 접속·Conda·Blender까지

상세 색인: [INDEX.md](INDEX.md)  
로컬 vs 서버 파일: [SERAPH_AND_LOCAL.md](SERAPH_AND_LOCAL.md)  
컨베이어 물리·실행: [CONVEYOR_DEMO.md](CONVEYOR_DEMO.md)

---

## 1. SSH

- 별칭 복붙: 레포의 `local/ssh_config_snippet_aurora_seraph.txt` → Windows `%USERPROFILE%\.ssh\config`
- 비밀번호: `local/aurora_seraph_credentials.txt` (Git 무시, 로컬만)

```bash
ssh aurora-seraph
```

---

## 2. Cursor Remote-SSH

F1 → `Remote-SSH: Connect to Host...` → `aurora-seraph` → Open Folder: `/data/minjae051213` (또는 `.../Tangerine`)

---

## 3. 레포

```bash
cd /data/minjae051213
git clone https://github.com/jsm0308/Tangerine.git   # 본인 URL
cd Tangerine
git pull
```

---

## 4. Python (sudo 없을 때: Conda 권장)

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

## 5. Blender

```bash
which blender
blender --version
```

없으면 관리자에게 경로 문의. `scripts/run_conveyor_demo.py` 에 `--blender /전체/경로` 가능.

---

## 6. 변종 GLB 전체 빌드 (Seraph)

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

---

## 7. 다음 단계 (컨베이어 등)

- 컨베이어: [CONVEYOR_DEMO.md](CONVEYOR_DEMO.md) §5

GPU 렌더는 `defaults.py` 의 `cycles_compute_device`; 드라이버 없으면 CPU로 떨어질 수 있음.
