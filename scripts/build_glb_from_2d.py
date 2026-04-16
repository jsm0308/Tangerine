#!/usr/bin/env python3
"""
트랙 2 — 2D(클래스 폴더 이미지) → 베이스 GLB.

기본: 병변 마스크·패치 전처리 후 UV 알베도에 스탬프 (Texture Paint식, decal.enabled: true)
  - 전처리: src/decal_prep/mask_and_patch.py  →  manifest + 패치 PNG
  - Blender: src/blender_sim/decal_mesh_export.py
  - 진입:    src/blender_sim/entries/decal_mesh_entry.py

레거시(BOX 투영 + 정점색): decal.enabled: false
  - src/blender_sim/fruit_class_mesh_export.py
  - src/blender_sim/entries/fruit_class_mesh_entry.py

  python scripts/build_glb_from_2d.py
  python scripts/build_glb_from_2d.py --config Generate_Tangerine_3D/from_2d_track/configs/from_2d_batch.yaml

산출: from_2d_batch.yaml 의 output_dir (기본 data/Tangerine_3D/glb_from_2d)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from config import load_pipeline_config, write_json  # noqa: E402

from src.decal_prep.mask_and_patch import build_decal_cache, load_decal_config_defaults  # noqa: E402

DEFAULT_CONFIG = "Generate_Tangerine_3D/from_2d_track/configs/from_2d_batch.yaml"


def _resolve_blender_exe(cfg) -> str:
    exe = (cfg.blender.blender_executable or "").strip()
    if exe and Path(exe).is_file():
        return exe
    return shutil.which("blender") or shutil.which("blender.exe") or ""


def _abs(root: Path, p: str | Path) -> Path:
    pp = Path(p)
    return pp.resolve() if pp.is_absolute() else (root / pp).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="2D 클래스 이미지 → GLB (트랙 2, data/Tangerine_3D/glb_from_2d)",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="from_2d_batch.yaml")
    parser.add_argument(
        "--pipeline-config",
        default="configs/default_config.yaml",
        help="Blender 실행 파일용",
    )
    args = parser.parse_args()

    if yaml is None:
        print("pip install pyyaml", file=sys.stderr)
        return 1

    os.chdir(ROOT)
    ypath = _abs(ROOT, args.config)
    if not ypath.is_file():
        print(f"설정 없음: {ypath}", file=sys.stderr)
        return 1

    with open(ypath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    pc = _abs(ROOT, args.pipeline_config)
    cfg = load_pipeline_config(str(pc) if pc.is_file() else None)
    blender_exe = _resolve_blender_exe(cfg)
    if not blender_exe:
        print("Blender 경로를 configs/default_config.yaml 에 설정하세요.", file=sys.stderr)
        return 1

    fruits_root = _abs(ROOT, data.get("fruits_root", "data/Tangerine_2D"))
    if not fruits_root.is_dir():
        print(
            f"없음: {fruits_root} — from_2d_batch.yaml 의 fruits_root 또는 data/Tangerine_2D 를 준비하세요.",
            file=sys.stderr,
        )
        return 1

    raw_meshes = data.get("mesh_paths") or []
    mesh_list: list[Path] = []
    missing: list[str] = []
    for p in raw_meshes:
        mp = _abs(ROOT, p)
        if mp.is_file():
            mesh_list.append(mp)
        else:
            missing.append(str(p))
    if missing:
        print(
            "[build_glb_from_2d] 다음 mesh_paths 가 없습니다 (폴백 없음 — 수정 후 다시 실행):",
            file=sys.stderr,
        )
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
    if not mesh_list:
        print(
            "베이스 GLB가 하나도 없습니다. from_2d_batch.yaml 의 mesh_paths 에 "
            "실제 파일 경로를 넣으세요 (예: data/Tangerine_3D/tangerine0.glb).",
            file=sys.stderr,
        )
        return 1
    if len(mesh_list) < 3:
        print(
            f"[build_glb_from_2d] 베이스 {len(mesh_list)}개만 있음 — 순환 사용합니다.",
            flush=True,
        )

    out = _abs(ROOT, data.get("output_dir", "data/Tangerine_3D/glb_from_2d"))
    out.mkdir(parents=True, exist_ok=True)

    decal_defaults = load_decal_config_defaults()
    decal_user = data.get("decal") or {}
    decal_cfg = {**decal_defaults, **decal_user}
    use_decal = bool(decal_cfg.get("enabled", True))

    job_path = ROOT / "Generate_Tangerine_3D" / "from_2d_track" / "last_job.json"
    job_path.parent.mkdir(parents=True, exist_ok=True)

    if use_decal:
        cache_root = _abs(ROOT, decal_cfg.get("cache_dir") or "Generate_Tangerine_3D/from_2d_track/decal_cache")
        print("[build_glb_from_2d] 데칼 캐시 생성 (마스크·패치)…", flush=True)
        cache_result = build_decal_cache(fruits_root, cache_root, decal_cfg)
        job = {
            "manifest_path": str(cache_result.manifest_path),
            "fruits_root": str(fruits_root),
            "mesh_paths": [str(p) for p in mesh_list],
            "output_root": str(out),
            "total_exports": int(data.get("total_exports", 15)),
            "resume": bool(data.get("resume", False)),
            "stamps_per_asset": int(
                decal_cfg.get("stamps_per_asset", decal_cfg.get("decals_per_asset", 4))
            ),
            "texture_resolution": int(decal_cfg.get("texture_resolution", 2048)),
            "stamp_uv_radius": float(decal_cfg.get("stamp_uv_radius", 0.06)),
            "use_healthy_albedo_base": bool(decal_cfg.get("use_healthy_albedo_base", True)),
        }
        write_json(job_path, job)
        entry = ROOT / "src" / "blender_sim" / "entries" / "decal_mesh_entry.py"
    else:
        job = {
            "fruits_root": str(fruits_root),
            "mesh_paths": [str(p) for p in mesh_list],
            "output_root": str(out),
            "total_exports": int(data.get("total_exports", 15)),
            "resume": bool(data.get("resume", False)),
        }
        write_json(job_path, job)
        entry = ROOT / "src" / "blender_sim" / "entries" / "fruit_class_mesh_entry.py"

    cmd = [blender_exe, "--background", "--python", str(entry), "--", str(job_path)]
    print("Blender:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    print(f"출력: {out}\n작업 JSON: {job_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
