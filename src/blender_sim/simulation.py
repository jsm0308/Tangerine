"""
Blender rigid-body citrus simulation and rendering.

Run only inside Blender (imports bpy). See blender_entry.py.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bpy
from mathutils import Vector


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _ensure_rigidbody_world() -> None:
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()


def _spawn_plane(name: str, size: Tuple[float, float], location: Vector, friction: float) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=2, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] / 2, size[1] / 2, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = 0.0
    return obj


def _spawn_citrus(
    index: int,
    location: Vector,
    gt_class: str,
    friction: float,
    restitution: float,
    rotation_jitter_deg: float,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, segments=32, ring_count=16, location=location)
    obj = bpy.context.active_object
    obj.name = f"Citrus_{index:03d}"
    obj["gt_disease_class"] = gt_class
    # Simple color coding by class for debugging
    mat = bpy.data.materials.new(name=f"Mat_{obj.name}")
    hue = (hash(gt_class) % 360) / 360.0
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (hue, 0.45, 0.15, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    rot_z = math.radians(random.uniform(-rotation_jitter_deg, rotation_jitter_deg))
    rot_x = math.radians(random.uniform(-rotation_jitter_deg, rotation_jitter_deg))
    obj.rotation_euler = (rot_x, 0.0, rot_z)
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = restitution
    obj.rigid_body.mass = 0.15
    return obj


def _setup_camera_light(
    exp: Dict[str, Any],
    blend: Dict[str, Any],
) -> Tuple[bpy.types.Object, bpy.types.Object]:
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    h_min = float(blend["camera_height_offset_min"])
    h_max = float(blend["camera_height_offset_max"])
    z_off = random.uniform(h_min, h_max)
    jitter = math.radians(float(blend["camera_jitter_deg"]))
    cam_obj.location = (
        random.uniform(-1.5, 1.5),
        random.uniform(-8.0, -5.0),
        z_off,
    )
    cam_obj.rotation_euler = (
        math.radians(75) + random.uniform(-jitter, jitter),
        0.0,
        random.uniform(-jitter, jitter),
    )

    light_data = bpy.data.lights.new(name="Light", type="POINT")
    le_min = float(blend["light_energy_min"])
    le_max = float(blend["light_energy_max"])
    light_data.energy = random.uniform(le_min, le_max)
    ct_min = float(blend["color_temperature_min"])
    ct_max = float(blend["color_temperature_max"])
    light_data.color = (1.0, 0.95, 0.9)  # simplified; full blackbody optional
    _ = (ct_min, ct_max)
    light_obj = bpy.data.objects.new("Light", light_data)
    scene.collection.objects.link(light_obj)
    lj = float(blend["light_location_jitter"])
    light_obj.location = (
        random.uniform(-lj, lj),
        random.uniform(-lj, lj),
        random.uniform(4.0, 8.0),
    )
    return cam_obj, light_obj


def _project_bbox_xyxy(
    scene: bpy.types.Scene,
    cam: bpy.types.Object,
    obj: bpy.types.Object,
    res_x: int,
    res_y: int,
) -> List[float]:
    from bpy_extras.object_utils import world_to_camera_view

    mat = obj.matrix_world
    corners = [mat @ Vector(c) for c in obj.bound_box]
    xs: List[float] = []
    ys: List[float] = []
    for world_coord in corners:
        co = world_to_camera_view(scene, cam, world_coord)
        if co.z < 0:
            continue
        x_px = co.x * res_x
        y_px = (1.0 - co.y) * res_y
        xs.append(x_px)
        ys.append(y_px)
    if not xs:
        return [0.0, 0.0, float(res_x), float(res_y)]
    xmin, xmax = max(0, min(xs)), min(res_x, max(xs))
    ymin, ymax = max(0, min(ys)), min(res_y, max(ys))
    return [xmin, ymin, xmax, ymax]


def run_simulation(cfg: Dict[str, Any]) -> None:
    """Main entry: build scene, simulate, render frames, write metadata JSONL."""
    exp = cfg["experiment"]
    blend = cfg["blender"]
    class_names: List[str] = list(cfg.get("inference_class_names") or ["Normal", "Canker", "Scab", "Black_spot"])

    random.seed(int(exp["seed"]))

    out_root = Path(exp["base_output_dir"]) / exp["experiment_id"]
    renders_dir = out_root / blend["renders_subdir"]
    renders_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_root / blend["metadata_filename"]

    _clear_scene()
    scene = bpy.context.scene
    scene.render.use_motion_blur = False
    scene.render.resolution_x = int(blend["render_width"])
    scene.render.resolution_y = int(blend["render_height"])
    scene.render.fps = int(blend["render_fps"])
    scene.frame_start = 1
    episode = int(blend["episode_frame_count"])
    scene.frame_end = episode
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    _ensure_rigidbody_world()
    if scene.rigidbody_world:
        rbw = scene.rigidbody_world
        fps_i = int(blend["render_fps"])
        if hasattr(rbw, "steps_per_second"):
            rbw.steps_per_second = max(60, fps_i * 2)
        elif hasattr(rbw, "substeps_per_frame"):
            sub = max(2, min(24, int(blend["physics_substeps"])))
            rbw.substeps_per_frame = sub
        if hasattr(rbw, "solver_iterations"):
            rbw.solver_iterations = max(10, int(blend["physics_substeps"]))

    belt_speed = float(blend["belt_speed"])
    # Belt plane (passive) — keyframed motion along +X
    belt = _spawn_plane("Belt", (14.0, 4.0), Vector((0, 0, -0.05)), friction=0.8)
    belt.location = Vector((-4.0, 0, 0))
    belt.keyframe_insert(data_path="location", frame=1)
    belt.location = Vector((-4.0 + belt_speed * episode / max(1, scene.render.fps), 0, 0))
    belt.keyframe_insert(data_path="location", frame=episode)

    # Side walls (passive) to keep fruit on belt
    wall_friction = 0.5
    wall_l = _spawn_plane("WallL", (8.0, 3.0), Vector((0, -2.0, 0.4)), wall_friction)
    wall_l.rotation_euler = (math.radians(90), 0, 0)
    wall_r = _spawn_plane("WallR", (8.0, 3.0), Vector((0, 2.0, 0.4)), wall_friction)
    wall_r.rotation_euler = (math.radians(90), 0, 0)

    count = int(blend["spawn_total"]) if blend.get("spawn_total") is not None else random.randint(
        int(blend["citrus_count_min"]),
        int(blend["citrus_count_max"]),
    )
    f_min = float(blend["rigid_body_friction_min"])
    f_max = float(blend["rigid_body_friction_max"])
    rest = float(blend["rigid_body_restitution"])
    rot_j = float(blend["citrus_initial_rotation_jitter_deg"])

    citrus_objs: List[bpy.types.Object] = []
    for i in range(count):
        gt = random.choice(class_names)
        loc = Vector(
            (
                random.uniform(-3.0, 1.0),
                random.uniform(-1.2, 1.2),
                random.uniform(1.5, 2.5),
            )
        )
        citrus_objs.append(
            _spawn_citrus(i, loc, gt, random.uniform(f_min, f_max), rest, rot_j)
        )

    cam, _light = _setup_camera_light(exp, blend)

    # Write metadata
    meta_lines: List[str] = []
    res_x = scene.render.resolution_x
    res_y = scene.render.resolution_y

    for frame in range(1, episode + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        scene.render.filepath = str(renders_dir / f"frame_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)

        for obj in citrus_objs:
            if "gt_disease_class" not in obj:
                continue
            bbox = _project_bbox_xyxy(scene, cam, obj, res_x, res_y)
            rec = {
                "frame_index": frame,
                "object_uid": obj.name,
                "gt_disease_class": obj["gt_disease_class"],
                "bbox_xyxy": bbox,
                "world_location": [obj.location.x, obj.location.y, obj.location.z],
            }
            meta_lines.append(json.dumps(rec, ensure_ascii=False))

    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("\n".join(meta_lines) + ("\n" if meta_lines else ""))

    print(f"[blender_sim] Wrote {renders_dir} and {meta_path}")
