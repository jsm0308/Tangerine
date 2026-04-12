"""
Generate `reports/{experiment_id}/`: crops, CSV tables, `report.md`, optional `report.html`.

Layout:
  reports/{Exp_ID}/
    report.md
    report.html          # if report.include_html
    crops/               # obj_{track_id}_f{frame:06d}.png
    figures/             # matplotlib outputs
    predictions_table.csv
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd

from config import PipelineConfig

logger = logging.getLogger(__name__)


def _iou(box_a: List[float], box_b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.is_file():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _match_gt(
    frame_idx: int,
    bbox: List[float],
    gt_by_frame: Dict[int, List[Dict[str, Any]]],
    iou_thresh: float = 0.2,
) -> Optional[str]:
    candidates = gt_by_frame.get(frame_idx, [])
    best_iou = 0.0
    best_gt: Optional[str] = None
    for g in candidates:
        gt_box = g.get("bbox_xyxy")
        if not gt_box:
            continue
        iou = _iou(bbox, [float(x) for x in gt_box])
        if iou > best_iou:
            best_iou = iou
            best_gt = str(g.get("gt_disease_class"))
    if best_iou >= iou_thresh and best_gt is not None:
        return best_gt
    return None


def run_report(cfg: PipelineConfig) -> Path:
    exp_dir = cfg.experiment_output_dir()
    rep_root = exp_dir / cfg.report.reports_subdir
    crops_dir = rep_root / "crops"
    fig_dir = rep_root / "figures"
    rep_root.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    pred_path = exp_dir / cfg.inference.predictions_jsonl
    meta_path = exp_dir / cfg.blender.metadata_filename
    img_dir = exp_dir / cfg.inference.inference_input_subdir

    preds = _load_jsonl(pred_path)
    meta_rows = _load_jsonl(meta_path)
    gt_by_frame: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for m in meta_rows:
        fi = int(m.get("frame_index", -1))
        if fi >= 0:
            gt_by_frame[fi].append(m)

    rows_csv: List[Dict[str, Any]] = []
    correct = 0
    total_matched = 0
    disease_counts: Dict[str, int] = defaultdict(int)
    thresh = float(cfg.inference.stats_disease_threshold)

    for rec in preds:
        fi = int(rec.get("frame_index", 0))
        img_name = rec.get("image", "")
        img_path = img_dir / img_name if img_name else None
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR) if img_path and img_path.is_file() else None

        for obj in rec.get("objects", []):
            tid = int(obj.get("track_id", -1))
            bbox = obj.get("bbox_xyxy", [0, 0, 0, 0])
            probs: Dict[str, float] = obj.get("disease_probs", {})
            top = obj.get("top_disease", "")
            matched_gt = _match_gt(fi, bbox, gt_by_frame)
            if matched_gt is not None:
                total_matched += 1
                if matched_gt == top:
                    correct += 1
            for cname, p in probs.items():
                if p >= thresh and cname != "Normal":
                    disease_counts[cname] += 1

            rows_csv.append(
                {
                    "frame_index": fi,
                    "track_id": tid,
                    "top_disease": top,
                    "matched_gt": matched_gt or "",
                    "alert": obj.get("alert", False),
                    **{f"prob_{k}": v for k, v in probs.items()},
                }
            )

            if img is not None:
                x1, y1, x2, y2 = [int(round(x)) for x in bbox]
                h, w = img.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 > x1 and y2 > y1:
                    crop = img[y1:y2, x1:x2]
                    mx = cfg.report.crop_resize_max
                    scale = min(mx / max(crop.shape[0], 1), mx / max(crop.shape[1], 1), 1.0)
                    if scale < 1.0:
                        crop = cv2.resize(
                            crop,
                            (int(crop.shape[1] * scale), int(crop.shape[0] * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    fn = crops_dir / f"obj_{tid:04d}_f{fi:06d}.png"
                    cv2.imwrite(str(fn), crop)

    df = pd.DataFrame(rows_csv)
    csv_path = rep_root / "predictions_table.csv"
    df.to_csv(csv_path, index=False)

    acc = (correct / total_matched) if total_matched else 0.0

    # matplotlib summary
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if disease_counts:
            plt.figure(figsize=(6, 4))
            plt.bar(list(disease_counts.keys()), list(disease_counts.values()))
            plt.title("Disease mentions above threshold")
            plt.xticks(rotation=30, ha="right")
            plt.tight_layout()
            plt.savefig(fig_dir / "disease_counts.png", dpi=cfg.report.matplotlib_dpi)
            plt.close()
    except Exception as e:
        logger.warning("matplotlib chart skipped: %s", e)

    md_lines = [
        f"# Experiment report: {cfg.experiment.experiment_id}",
        "",
        "## Summary",
        "",
        f"- Matched GT rows (IoU): {total_matched}",
        f"- Top-1 accuracy vs matched GT: **{acc:.2%}**",
        f"- Disease threshold for stats: {thresh}",
        "",
        "## Per-object table",
        "",
        f"See [`predictions_table.csv`](predictions_table.csv).",
        "",
        "## Crops",
        "",
        "Saved under `crops/` as `obj_{track_id}_f{frame}.png`.",
        "",
    ]
    if disease_counts:
        md_lines.append("![disease counts](figures/disease_counts.png)")
        md_lines.append("")

    report_md = rep_root / "report.md"
    report_md.write_text("\n".join(md_lines), encoding="utf-8")

    if cfg.report.include_html:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape

            env = Environment(
                loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
                autoescape=select_autoescape(["html", "xml"]),
            )
            tpl = env.get_template("report.html.j2")
            html = tpl.render(
                experiment_id=cfg.experiment.experiment_id,
                accuracy=acc,
                total_matched=total_matched,
                disease_counts=dict(disease_counts),
                csv_name="predictions_table.csv",
            )
            (rep_root / "report.html").write_text(html, encoding="utf-8")
        except Exception as e:
            logger.warning("HTML report skipped (install jinja2?): %s", e)

    logger.info("Report written to %s", rep_root)
    return rep_root
