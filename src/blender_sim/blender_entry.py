"""
Invoke from project root:

  blender --background --python src/blender_sim/blender_entry.py -- path/to/blender_config.json

`main.py --stage blender` writes `blender_config.json` under the experiment output dir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Custom args after "--"
if "--" not in sys.argv:
    print("Usage: blender --background --python src/blender_sim/blender_entry.py -- blender_config.json")
    sys.exit(1)

cfg_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.blender_sim.simulation import run_simulation  # noqa: E402

with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

run_simulation(cfg)
