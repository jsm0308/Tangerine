# Seraph 서버에서 Tangerine

큰 바이너리(GLB 등)는 Git에 넣지 않고 **로컬 ↔ Seraph를 rsync/WinSCP**로 맞춘 뒤, 서버에서 `git pull` 한다.

## Git

```bash
cd /path/to/Tangerine
git pull origin main
```

원격 루트 예: `SERAPH_REPO_ROOT` 기본값 `scripts/seraph_build_glb_from_2d_remote.py` 에 ` /data/minjae051213/Tangerine` (환경에 맞게 수정).

## SSH · Conda · Blender

- SSH: `~/.ssh/config`에 `Host`(예: `aurora-seraph`)·키 등록.
- Conda: `conda activate tangerine` 후 스크립트 실행.
- Blender: `configs/default_config.yaml`의 `blender.blender_executable`을 **Seraph의 `blender` 경로**로 둔다.

## 트랙별 실행

| 목적 | 문서 / 스크립트 |
|------|-----------------|
| 2D → GLB (GPU 권장) | [Generate_Tangerine_3D/from_2d_track/README.md](../Generate_Tangerine_3D/from_2d_track/README.md), `scripts/seraph_build_glb_from_2d_remote.py` |
| 절차 변종 GLB | [3D_GENERATION_NOTES.md](3D_GENERATION_NOTES.md), `scripts/seraph_build_variant_glb.sh`, `scripts/generate_variants_build.py` |

베이스 메시는 `data/Tangerine_3D/tangerine_0.glb` ~ `tangerine_2.glb`(레포에는 없음; 로컬·Seraph에 복사).
