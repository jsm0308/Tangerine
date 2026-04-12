#!/usr/bin/env bash
# Aurora/Ubuntu: run after main.py has written blender_config.json
#   python main.py --stage blender --config configs/default_config.yaml
# Or invoke manually:
#   ./scripts/run_blender_headless.sh outputs/Exp_001/blender_config.json
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${1:-$ROOT/outputs/Exp_001/blender_config.json}"
exec blender --background --python "$ROOT/src/blender_sim/blender_entry.py" -- "$CFG"
