# 로컬 PC vs Seraph(Aurora) — 무엇을 어디에 두나

같은 GitHub 레포를 **로컬에서 편집**하고 **Seraph에서 무거운 Blender·렌더**를 돌리는 경우를 기준으로 정리한다.

---

## 한눈 표


| 항목               | 로컬 (Windows 등)                                                 | Seraph (`/data/minjae051213/...`)                               |
| ---------------- | -------------------------------------------------------------- | --------------------------------------------------------------- |
| **레포 소스**        | `git clone` / 작업 폴더                                            | `git clone` 동일 레포 (예: `Tangerine/`)                             |
| **Python**       | 로컬 venv 또는 시스템 Python                                          | **Conda** 환경 `tangerine` (`~/miniconda3/envs/tangerine`)        |
| **비밀번호·SSH**     | `local/aurora_seraph_credentials.txt` (**Git 무시**)             | 해당 파일은 **올리지 않음** — 필요 시 로컬에서만 보관·복사                            |
| **SSH 별칭 예시**    | `local/ssh_config_snippet_aurora_seraph.txt` → `~/.ssh/config` | 접속 **대상** (서버 쪽에 별도 저장 불필요)                                     |
| **대용량 학습 이미지**   | `data/Fruits/` 등 (**Git에 포함 안 함**)                             | 필요하면 **직접 복사·rsync** (레포에 없음)                                   |
| **Blender**      | 설치 경로 또는 `BLENDER_EXECUTABLE`                                  | `which blender` 또는 관리자 지정 경로                                    |
| **산출물 (실험 결과)**  | `outputs/...` (로컬 실행 시)                                        | `outputs/...` (**Seraph 디스크에 저장** — 컨베이어 MP4, `_variant_glb` 등) |
| **GLB 에셋 (생성됨)** | 로컬에서 빌드 시 로컬 `outputs/`·`assets/glb/`                          | Seraph에서 빌드 시 **Seraph 경로에만** 생김 — 로컬과 자동 동기화 **안 됨**           |


---

## 동기화 원칙

1. **코드·설정** → **Git** (`git push` / Seraph에서 `git pull`).
2. **생성된 GLB·영상·대용량 데이터** → Git에 넣지 않거나(`.gitignore`), 필요 시 **수동 복사·별도 스토리지**.
3. Seraph에서 만든 `outputs/conveyor_demo/conveyor_run.mp4` 를 로컬로 가져오려면 **scp/rsync** 또는 Cursor로 파일 다운로드.

---

## 권장 작업 방식

- **한 번에 하나의 무거운 작업** (Blender GPU 렌더 2개 동시 실행은 GPU·큐 경합 가능).  
- 컨베이어 데모는 **입력 GLB가 Seraph 경로에 존재**해야 한다 (`defaults.py` 의 `citrus_glb_directory` / `citrus_glb_paths`).

---

## 변종 GLB를 Seraph에서 만들기

- 셸: `scripts/seraph_build_variant_glb.sh` (Seraph에서 실행)
- 로컬에서 SSH로 돌리기: `python scripts/seraph_build_variants_remote.py` ([SERAPH_REMOTE_GUIDE.md](SERAPH_REMOTE_GUIDE.md) §6)

## 관련 문서

- 절차: [SERAPH_REMOTE_GUIDE.md](SERAPH_REMOTE_GUIDE.md)  
- 컨베이어·물리·캐시: [CONVEYOR_DEMO.md](CONVEYOR_DEMO.md)

