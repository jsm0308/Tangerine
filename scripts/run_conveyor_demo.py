#!/usr/bin/env python3
"""호환 진입점: 실제 구현은 Conveyor_Lab/scripts/run_conveyor_demo.py 입니다."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "Conveyor_Lab" / "scripts" / "run_conveyor_demo.py"

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, str(TARGET), *sys.argv[1:]]))
