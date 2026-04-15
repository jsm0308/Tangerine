"""Map predictions to route ids and emit actuation signals."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from config import PipelineConfig
from .drivers import ActuationDriver, make_driver

logger = logging.getLogger(__name__)


def _route_for_disease(top_disease: str, rules: Dict[str, str]) -> str:
    if top_disease in rules:
        return str(rules[top_disease])
    return str(rules.get("default", "line_accept"))


def run_postprocess(cfg: PipelineConfig) -> Path:
    """
    Read `predictions.jsonl`, apply routing rules per `top_disease`, write actuation signals.
    """
    exp_dir = cfg.experiment_output_dir()
    pred_path = exp_dir / cfg.inference.predictions_jsonl
    if not pred_path.is_file():
        raise FileNotFoundError(f"Missing predictions: {pred_path}")

    post = cfg.postprocess
    rules = dict(post.routing_rules or {})
    out_name = post.actuation_signals_jsonl
    driver: ActuationDriver = make_driver(post.driver, exp_dir, out_name)
    out_path = exp_dir / out_name

    last_route: Dict[int, str] = {}
    n_emitted = 0

    try:
        with open(pred_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                frame_index = int(rec.get("frame_index", 0))
                tick_index = rec.get("tick_index", frame_index)
                if tick_index is None:
                    tick_index = frame_index
                for obj in rec.get("objects", []):
                    tid = int(obj.get("track_id", -1))
                    top = str(obj.get("top_disease", "default"))
                    route = _route_for_disease(top, rules)
                    if post.emit_on_route_change_only:
                        prev: Optional[str] = last_route.get(tid)
                        if prev == route:
                            continue
                        last_route[tid] = route

                    sig: Dict[str, Any] = {
                        "frame_index": frame_index,
                        "tick_index": tick_index,
                        "track_id": tid,
                        "route": route,
                        "top_disease": top,
                    }
                    if "belt_slot_index" in obj:
                        sig["belt_slot_index"] = obj["belt_slot_index"]
                    driver.emit(sig)
                    n_emitted += 1
    finally:
        driver.close()

    logger.info("Wrote %s actuation signals to %s", n_emitted, out_path)
    return out_path
