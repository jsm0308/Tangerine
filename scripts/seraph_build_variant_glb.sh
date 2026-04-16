#!/usr/bin/env bash
# Seraph(Aurora)에서 실행: 베이스 GLB → 변종 GLB(기본 15; variants_batch.yaml 기준) 빌드.
#
#   chmod +x scripts/seraph_build_variant_glb.sh
#   ./scripts/seraph_build_variant_glb.sh
#
# 환경 변수:
#   SERAPH_REPO_ROOT   레포 루트 (기본: /data/minjae051213/Tangerine)
#   SERAPH_GIT_PULL=1    실행 전 git pull (선택)
#   CONDA_SH             conda.sh 경로 (기본: ~/miniconda3/etc/profile.d/conda.sh)

set -euo pipefail

ROOT="${SERAPH_REPO_ROOT:-/data/minjae051213/Tangerine}"
CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"

cd "$ROOT"
echo "[seraph_build_variant_glb] cwd=$(pwd)"

if [[ "${SERAPH_GIT_PULL:-0}" == "1" ]]; then
  echo "[seraph_build_variant_glb] git pull"
  git pull
fi

if [[ -f "$CONDA_SH" ]]; then
  # shellcheck source=/dev/null
  source "$CONDA_SH"
else
  echo "[seraph_build_variant_glb] WARN: conda.sh 없음 — 이미 conda activate 된 터미널에서 실행했는지 확인" >&2
fi

if command -v conda >/dev/null 2>&1; then
  conda activate tangerine
fi

export PYTHONUNBUFFERED=1

echo "[seraph_build_variant_glb] gen_disease_texture_masks"
python scripts/gen_disease_texture_masks.py

echo "[seraph_build_variant_glb] build_base_mesh"
python scripts/build_base_mesh.py

echo "[seraph_build_variant_glb] generate_variants_build"
python scripts/generate_variants_build.py

echo "[seraph_build_variant_glb] done → data/Tangerine_3D/glb_procedural/ manifest.json"
