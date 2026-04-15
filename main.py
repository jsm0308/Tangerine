#!/usr/bin/env python3
"""
Smart factory synthetic data & diagnosis pipeline — CLI entry.

See README.md and docs/PIPELINE.md for repository layout and full data flow.

Stages:
  blender   — Headless Blender sim + renders + frame_metadata.jsonl (requires `blender` on PATH or config.blender_executable).
  augment   — 2D augmentation on rendered PNGs.
  infer     — Modular vision (YOLO / Mask R-CNN) + track + disease probs; writes predictions.jsonl.
  postprocess — Route predictions to logical actuation signals (JSONL/print/noop).
  report    — Crops, CSV, Markdown/HTML under outputs/{Exp_ID}/reports/.
  all       — augment → infer → report (run `--stage blender` first if renders are missing).
  vision_all — augment → infer → postprocess (no HTML report).

Examples:
  python main.py --stage blender --config configs/default_config.yaml
  python main.py --stage all --config configs/default_config.yaml
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import dump_blender_job, load_pipeline_config  # noqa: E402


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _run_blender(cfg) -> None:
    dump_blender_job(cfg)
    json_path = cfg.blender_config_path()
    exe = (cfg.blender.blender_executable or "").strip() or shutil.which("blender") or shutil.which("blender.exe")
    if not exe:
        raise RuntimeError(
            "Blender executable not found. Set blender.blender_executable in config or install Blender and add to PATH."
        )
    entry = ROOT / "src" / "blender_sim" / "entries" / "blender_entry.py"
    cmd = [exe, "--background", "--python", str(entry), "--", str(json_path)]
    logging.getLogger(__name__).info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart factory synthetic pipeline")
    parser.add_argument(
        "--stage",
        choices=("blender", "augment", "infer", "postprocess", "report", "all", "vision_all"),
        required=True,
        help="Pipeline stage to run",
    )
    parser.add_argument("--config", default=None, help="Optional YAML override")
    args = parser.parse_args()

    cfg = load_pipeline_config(args.config)
    _setup_logging(cfg.experiment.log_level)

    if args.stage == "blender":
        _run_blender(cfg)
        return

    from src.augment.pipeline import run_augmentation  # noqa: WPS433
    from src.inference.pipeline import run_inference  # noqa: WPS433
    from src.postprocess.logical_queue import run_postprocess  # noqa: WPS433
    from src.reporting.generate import run_report  # noqa: WPS433

    if args.stage == "augment":
        run_augmentation(cfg)
    elif args.stage == "infer":
        run_inference(cfg)
    elif args.stage == "postprocess":
        run_postprocess(cfg)
    elif args.stage == "report":
        run_report(cfg)
    elif args.stage == "all":
        run_augmentation(cfg)
        run_inference(cfg)
        run_report(cfg)
    elif args.stage == "vision_all":
        run_augmentation(cfg)
        run_inference(cfg)
        run_postprocess(cfg)


if __name__ == "__main__":
    main()
