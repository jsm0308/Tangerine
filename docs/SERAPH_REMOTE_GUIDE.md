# Seraph(Aurora) 원격에서 Tangerine — SSH 별칭부터 객체(GLB·컨베이어) 생성까지

로컬 Cursor에서만 작업하지 않고 **서버 GPU/장시간 작업**을 쓰려는 경우의 순서입니다.

---

## 1. SSH 별칭 붙여넣기

1. 레포 안 **`local/ssh_config_snippet_aurora_seraph.txt`** 를 연다.  
2. 파일 안에 적힌 대로 **`Host aurora-seraph` 블록 전체**를 복사한다.  
3. Windows에서 **`%USERPROFILE%\.ssh\config`** (예: `C:\Users\이름\.ssh\config`) 파일을 연다.  
   - `.ssh` 폴더나 `config`가 없으면 새로 만든다.  
4. 복사한 블록을 **파일 끝에 붙여넣고 저장**한다.  
5. 비밀번호·계정 요약은 **`local/aurora_seraph_credentials.txt`** 한 파일만 사용한다 (Git에 안 올라감).

터미널에서 확인:

```bash
ssh aurora-seraph
```

처음이면 호스트 키 확인 → 비밀번호 입력 → 접속되면 `exit` 로 나온다.

---

## 2. Cursor에서 원격 폴더로 열기 (Remote-SSH)

1. Cursor에서 **F1** → **`Remote-SSH: Connect to Host...`**  
2. **`aurora-seraph`** 선택 (config에 넣었으면 목록에 뜸).  
3. 연결되면 **File → Open Folder** 로 원격 경로 연다:  
   **`/data/minjae051213`**  
   (여기 아래에 레포를 둘 예정이면 그 하위 `Tangerine` 등을 연다.)

로컬과 달리 **에디터·통합 터미널이 전부 서버 기준**이다.

---

## 3. 서버에 레포 두기

원격 터미널에서:

```bash
cd /data/minjae051213
# 이미 있다면 생략
git clone <본인_레포_URL> Tangerine
cd Tangerine
```

또는 로컬에서 `scp`/`rsync`로 동기화해도 된다.

---

## 4. Python 환경

```bash
cd /data/minjae051213/Tangerine
python3 -m venv .venv
source .venv/bin/activate   # Windows 원격이면 보통 bash 기준
pip install -r requirements.txt
```

---

## 5. Blender (필수)

컨베이어 데모·GLB 빌드는 **Blender CLI**가 필요하다.

```bash
which blender
blender --version
```

없으면 서버 관리자/문서에 맞게 설치하거나, `BLENDER_EXECUTABLE` 환경 변수로 **실행 파일 전체 경로**를 지정한다.

`scripts/run_conveyor_demo.py` 는 `PATH`의 `blender` 또는 `--blender /path/to/blender` 를 쓴다.

---

## 6. “객체 만들기” 두 갈래 (무엇을 만들지에 따라)

### A. 병해·형태 **변종 GLB** (에셋 생성)

메인 실험 `main.py`와 별개로, **GLB 파일을 대량 생성**하는 경로다.

| 순서 | 명령 (레포 루트에서) | 산출물 (기본) |
|------|---------------------|----------------|
| 베이스 3종 | `python scripts/build_base_mesh.py` (`configs/base_mesh.yaml`) | `assets/glb/*.glb` |
| 변종 배치 | `python scripts/generate_variants_build.py` | `outputs/_variant_glb/*.glb` + `manifest.json` |

자세한 역할은 [PIPELINE.md](PIPELINE.md) 표 **B / B1 / B2**.

### B. **롤러 컨베이어** 영상·물리 데모 (귤 GLB를 벨트에 올림)

입력 GLB는 `src/blender_sim/conveyor_demo/defaults.py` 의  
`citrus_glb_directory` / `citrus_glb_paths` 규칙을 따른다.  
변종을 쓰려면 디렉터리에 GLB가 채워져 있어야 한다.

```bash
cd /data/minjae051213/Tangerine
source .venv/bin/activate
# 예: 짧게 시험
python scripts/run_conveyor_demo.py --out outputs/conveyor_demo --frames 120 --cycles 8 --blender "$(which blender)"
# MP4 + .blend 같이
python scripts/run_conveyor_demo.py --out outputs/conveyor_demo --also-blend --frames 120 --cycles 8
```

출력: `outputs/conveyor_demo/conveyor_run.mp4` , (옵션) `conveyor_scene.blend`  
설명·옵션 요약은 루트 [README.md](../README.md) 의 컨베이어 절.

---

## 7. GPU 렌더(Cycles)

데모 설정에 `cycles_compute_device`: `"GPU"` 가 있으면 Blender가 GPU를 쓴다.  
서버에 NVIDIA 드라이버·CUDA/OPTIX가 맞아야 하며, 없으면 CPU로 떨어질 수 있다.

---

## 8. 정리 — “그 뒤에 하려던 것”

1. **SSH 별칭**으로 접속을 편하게 만들고  
2. **Cursor Remote-SSH**로 `/data/minjae051213` 에서 레포를 연 뒤  
3. **객체(GLB)** 는 **B1→B2** 스크립트로 만들거나, 이미 있는 GLB를 두고  
4. **컨베이어 영상**은 `run_conveyor_demo.py` 로 서버에서 렌더·물리까지 돌린다.

문제가 나면 서버에서 `blender` 경로·디스크 용량·GPU (`nvidia-smi`) 를 먼저 확인하면 된다.
