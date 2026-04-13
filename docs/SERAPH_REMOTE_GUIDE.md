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

## 6. 다음 단계

- 변종 GLB: `python scripts/generate_variants_build.py` → `outputs/_variant_glb/`
- 컨베이어: [CONVEYOR_DEMO.md](CONVEYOR_DEMO.md) §5

GPU 렌더는 `defaults.py` 의 `cycles_compute_device`; 드라이버 없으면 CPU로 떨어질 수 있음.
