# src/blender_sim/render_glb_thumbnail.py
"""
헤드리스 Blender로 GLB 하나를 PNG로 렌더(품질 검사·미리보기용).

  blender --background --factory-startup --python src/blender_sim/render_glb_thumbnail.py \\
      -- path/to/model.glb path/to/out.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _bounds_world(objects: list) -> tuple[Vector, Vector]:
    min_c = Vector((1e9, 1e9, 1e9))
    max_c = Vector((-1e9, -1e9, -1e9))
    for o in objects:
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            min_c = Vector((min(min_c.x, w.x), min(min_c.y, w.y), min(min_c.z, w.z)))
            max_c = Vector((max(max_c.x, w.x), max(max_c.y, w.y), max(max_c.z, w.z)))
    return min_c, max_c


def main() -> None:
    if "--" not in sys.argv:
        print("Usage: blender ... -- glb_path out.png", flush=True)
        raise SystemExit(2)
    i = sys.argv.index("--") + 1
    glb_path = Path(sys.argv[i]).resolve()
    png_path = Path(sys.argv[i + 1]).resolve()
    png_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb_path))

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        print("[thumbnail] no mesh", flush=True)
        raise SystemExit(3)

    min_c, max_c = _bounds_world(meshes)
    center = (min_c + max_c) * 0.5
    size = (max_c - min_c).length
    if size < 1e-6:
        size = 1.0

    # 작은 메시에서 카메라가 물체 안에 들어가 배경만 찍히는 것 방지
    dist = max(size * 2.4, 0.55)
    offset = Vector((1.25, -1.55, 1.05)).normalized() * dist
    bpy.ops.object.camera_add(location=center + offset)
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam
    forward = center - cam.location
    if forward.length > 1e-8:
        cam.rotation_euler = forward.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 43.0

    bpy.ops.object.light_add(type="AREA", location=center + Vector((-0.9, 0.6, 1.6)).normalized() * dist * 0.85)
    L1 = bpy.context.active_object
    L1.data.energy = 1200.0
    if hasattr(L1.data, "size"):
        L1.data.size = max(size * 2.5, 0.5)
    bpy.ops.object.light_add(type="AREA", location=center + Vector((1.0, -0.8, 0.4)).normalized() * dist * 0.75)
    L2 = bpy.context.active_object
    L2.data.energy = 550.0
    if hasattr(L2.data, "size"):
        L2.data.size = max(size * 1.5, 0.35)

    scene = bpy.context.scene
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    try:
        world.color = (0.58, 0.58, 0.59)
    except Exception:
        pass

    # EEVEE/Next 는 일부 Intel GPU 드라이버에서 크래시 → QC용은 Cycles CPU 로 고정
    scene.render.engine = "CYCLES"
    if hasattr(scene.cycles, "device"):
        try:
            scene.cycles.device = "CPU"
        except Exception:
            pass
    scene.cycles.samples = 16
    if hasattr(scene.cycles, "use_adaptive_sampling"):
        scene.cycles.use_adaptive_sampling = True

    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.film_transparent = False
    scene.render.filepath = str(png_path)
    bpy.ops.render.render(write_still=True)
    print(f"[thumbnail] wrote {png_path}", flush=True)


if __name__ == "__main__":
    main()
