"""
Blender에서만 실행 — 프로시저 컨베이어 메시를 GLB로 내보냄 (물리·과일·렌더 없음).

  blender --background --factory-startup --python src/blender_sim/entries/conveyor_glb_export_entry.py -- path/to/conveyor_glb_export.json

JSON은 `merge_config` 결과: `defaults.py` 키 + `export_glb_filename`, `output_dir`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if "--" not in sys.argv:
    print(
        "Usage: blender --background --factory-startup --python "
        "src/blender_sim/entries/conveyor_glb_export_entry.py -- conveyor_glb_export.json"
    )
    sys.exit(1)

cfg_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import bpy  # noqa: E402

from src.blender_sim.conveyor.defaults import merge_config  # noqa: E402
from src.blender_sim.conveyor.conveyor_mesh import build_conveyor  # noqa: E402
from src.blender_sim.conveyor.conveyor_pitch import apply_conveyor_pitch  # noqa: E402


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def run_export(raw_cfg: dict) -> None:
    cfg = merge_config(raw_cfg)
    out_dir = Path(cfg["output_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = (cfg.get("export_glb_filename") or "conveyor_belt.glb").strip()
    if not name.lower().endswith(".glb"):
        name += ".glb"
    out_path = (out_dir / name).resolve()

    _clear_scene()
    scene = bpy.context.scene
    build = build_conveyor(scene, cfg)
    apply_conveyor_pitch(scene, build, cfg)

    to_export = list(build.roller_objects) + list(build.static_objects)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in to_export:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = to_export[0]

    bpy.ops.export_scene.gltf(
        filepath=str(out_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_materials="EXPORT",
    )
    print(f"Wrote conveyor GLB: {out_path}")


with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

run_export(cfg)
