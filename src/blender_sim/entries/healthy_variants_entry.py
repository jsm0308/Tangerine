"""
  blender --background --python src/blender_sim/entries/healthy_variants_entry.py -- job.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if "--" not in sys.argv:
    print(
        "Usage: blender --background --python src/blender_sim/entries/healthy_variants_entry.py -- job.json",
        file=sys.stderr,
    )
    sys.exit(1)

cfg_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.blender_sim.healthy_variants_export import run_healthy_variants_export  # noqa: E402

with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

try:
    run_healthy_variants_export(cfg)
except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    sys.exit(1)
