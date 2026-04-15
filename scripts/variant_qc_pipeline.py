#!/usr/bin/env python3
"""
변종 GLB 빌드 → 미리보기 PNG 렌더 → 수치 QC → 실패 시 disease_params 자동 보정 후 재빌드(루프).

  python scripts/variant_qc_pipeline.py
  python scripts/variant_qc_pipeline.py --max-iter 4

선행: Blender, PyYAML, Pillow, numpy. 산출은 variants_batch 의 output_dir(기본 outputs/_variant_glb).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from config import load_pipeline_config  # noqa: E402


def _blender_exe(cfg) -> str:
    e = (cfg.blender.blender_executable or "").strip()
    if e and Path(e).is_file():
        return e
    return shutil.which("blender") or shutil.which("blender.exe") or ""


def _qc_crop_rgba(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    cy, cx = h // 2, w // 2
    sh, sw = int(h * 0.42), int(w * 0.42)
    return arr[cy - sh // 2 : cy + sh // 2, cx - sw // 2 : cx + sw // 2]


def qc_disease(path: Path, disease: str) -> tuple[bool, dict]:
    crop = _qc_crop_rgba(path)
    r = float(crop[..., 0].mean())
    g = float(crop[..., 1].mean())
    b = float(crop[..., 2].mean())
    L = 0.299 * crop[..., 0] + 0.587 * crop[..., 1] + 0.114 * crop[..., 2]
    edge = float(
        np.abs(crop[1:, :, :] - crop[:-1, :, :]).mean()
        + np.abs(crop[:, 1:, :] - crop[:, :-1, :]).mean()
    )

    info: dict = {"mean_rgb": (r, g, b), "edge_energy": edge}
    flat = crop.reshape(-1, 3)
    if disease == "greening":
        gmr = flat[:, 1] - flat[:, 0]
        p60 = float(np.percentile(gmr, 60))
        p75 = float(np.percentile(gmr, 75))
        eps = 1.5 / 255.0
        frac_g = float((flat[:, 1] > flat[:, 0] + eps).mean())
        # 8비트 PNG·균일 조명에서 평균 RGB는 붕괴 → G>R 픽셀 비율 + 분위수 병행
        # greening 은 국소 패치라 G>R 픽셀 비율이 낮을 수 있음(3~8% 정도 기대)
        ok = frac_g > 0.032 or p60 > 0.004 or (p75 > 0.01 and float(gmr.mean()) > 0.0006)
        info["g_minus_r_mean"] = float(gmr.mean())
        info["g_minus_r_p60"] = p60
        info["frac_g_gt_r"] = frac_g
        return ok, info
    if disease == "black_spot":
        dark_frac = float((L < 0.38).mean())
        info["dark_frac"] = dark_frac
        return dark_frac > 0.028, info
    if disease == "healthy":
        # 오렌지 계열: R 이 G,B 보다 앞서야 함(조명에 무뎌져도 채널 우세)
        ok = r >= max(g, b) - 0.035 and (r + g) > (b + 0.04)
        return ok, info
    if disease in ("canker", "scab"):
        # 과도한 단색·무변화만 피함
        var = float(crop.reshape(-1, 3).std(axis=0).mean())
        info["rgb_var"] = var
        return var > 0.018, info
    return True, info


def render_one(exe: str, glb: Path, png: Path) -> None:
    thumb = ROOT / "src" / "blender_sim" / "render_glb_thumbnail.py"
    cmd = [
        exe,
        "--background",
        "--factory-startup",
        "--python",
        str(thumb),
        "--",
        str(glb.resolve()),
        str(png.resolve()),
    ]
    subprocess.run(cmd, check=True)


def apply_fail_tweaks(working: dict, failures: dict[str, dict]) -> None:
    dp = working.setdefault("disease_params", {})
    if "greening" in failures:
        g = dp.setdefault("greening", {})
        g["overlay_strength"] = float(g.get("overlay_strength", 0.88)) + 0.07
        g["greening_boost"] = float(g.get("greening_boost", 1.25)) + 0.12
        g["mottle_ramp_hi"] = min(0.92, float(g.get("mottle_ramp_hi", 0.82)) + 0.04)
    if "black_spot" in failures:
        b = dp.setdefault("black_spot", {})
        b["spot_mix_boost"] = float(b.get("spot_mix_boost", 1.2)) + 0.18
        b["voronoi_scale"] = max(55.0, float(b.get("voronoi_scale", 95.0)) - 18.0)
        b["spot_ramp_pos"] = min(0.55, float(b.get("spot_ramp_pos", 0.32)) + 0.06)
    if any(k in failures for k in ("canker", "scab", "healthy")):
        working["gltf_bake_size"] = min(4096, int(working.get("gltf_bake_size", 2048)) + 256)


def main() -> int:
    p = argparse.ArgumentParser(description="Build variant GLBs with QC loop")
    p.add_argument("--config", default="data/Tangerine_3D/configs/variants_batch.yaml")
    p.add_argument("--pipeline-config", default="configs/default_config.yaml")
    p.add_argument("--max-iter", type=int, default=4)
    p.add_argument("--base-mesh", default="tangerine0", help="QC 미리보기에 쓸 베이스 이름")
    args = p.parse_args()

    if yaml is None:
        print("pip install pyyaml", file=sys.stderr)
        return 1

    os.chdir(ROOT)
    pc = Path(args.pipeline_config)
    if not pc.is_absolute():
        pc = ROOT / pc
    cfg = load_pipeline_config(str(pc) if pc.is_file() else None)
    exe = _blender_exe(cfg)
    if not exe:
        print("Blender 경로를 설정하세요.", file=sys.stderr)
        return 1

    ypath = Path(args.config)
    if not ypath.is_absolute():
        ypath = ROOT / ypath
    with open(ypath, "r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)

    diseases = list((base_cfg.get("disease_params") or {}).keys())
    out_dir = Path(base_cfg.get("output_dir", "outputs/_variant_glb"))
    if not out_dir.is_absolute():
        out_dir = (ROOT / out_dir).resolve()

    qc_dir = out_dir / "_qc_previews"
    qc_dir.mkdir(parents=True, exist_ok=True)

    working = copy.deepcopy(base_cfg)
    last_failures: dict[str, dict] = {}

    for it in range(args.max_iter):
        print(f"\n=== QC iteration {it + 1}/{args.max_iter} ===", flush=True)

        def _abs(p: str) -> str:
            pp = Path(p)
            return str(pp.resolve() if pp.is_absolute() else (ROOT / pp).resolve())

        job = copy.deepcopy(working)
        job["output_dir"] = _abs(job["output_dir"])
        for src in job.get("glb_sources") or []:
            src["path"] = _abs(src["path"])

        out_dir.mkdir(parents=True, exist_ok=True)
        job_path = out_dir / "_resolved_job.json"
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=2, ensure_ascii=False)

        gen = ROOT / "src" / "blender_sim" / "generate_variants.py"
        subprocess.run(
            [exe, "--background", "--factory-startup", "--python", str(gen), "--", "--job-json", str(job_path)],
            check=True,
        )

        failures: dict[str, dict] = {}
        for dis in diseases:
            glb_name = f"{args.base_mesh}__{dis}.glb"
            glb_path = out_dir / glb_name
            if not glb_path.is_file():
                print(f"[QC] missing {glb_path}", flush=True)
                failures[dis] = {"error": "missing_glb"}
                continue
            png_path = qc_dir / f"iter{it}_{dis}.png"
            try:
                render_one(exe, glb_path, png_path)
            except subprocess.CalledProcessError as e:
                failures[dis] = {"error": str(e)}
                continue
            ok, info = qc_disease(png_path, dis)
            print(f"  {dis}: {'OK' if ok else 'FAIL'} {info}", flush=True)
            if not ok:
                failures[dis] = info

        if not failures:
            print("\n[QC] 모든 검사 통과. 종료.", flush=True)
            if it > 0:
                with open(ypath, "w", encoding="utf-8") as f:
                    yaml.safe_dump(working, f, allow_unicode=True, sort_keys=False)
                print(f"[QC] 조정된 disease_params 를 저장했습니다 → {ypath}", flush=True)
            return 0

        last_failures = failures
        apply_fail_tweaks(working, failures)

    print("\n[QC] 최대 반복 후에도 일부 실패:", last_failures, flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
