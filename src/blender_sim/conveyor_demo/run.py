"""
컨베이어 데모: 씬 빌드 → 물리 → 대각선 카메라 → 프레임마다 스폰 + 렌더.
중간 PNG는 `renders_subdir`(기본 `_tmp_frames`)에만 저장; 최종 MP4는 호스트 스크립트가 합성.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List

import bpy
from mathutils import Vector

from src.blender_sim.conveyor_demo import defaults
from src.blender_sim.conveyor_demo import physics as phys
from src.blender_sim.conveyor_demo.cycles_gpu import configure_cycles_device
from src.blender_sim.conveyor_demo.camera import (
    setup_diagonal_camera,
    setup_factory_lights,
    setup_top_down_camera,
    setup_world_background,
)
from src.blender_sim.conveyor_demo.conveyor_mesh import build_conveyor
from src.blender_sim.conveyor_demo.objects.fruit import (
    build_citrus_glb_sequence,
    build_glb_template,
    create_fruit_object,
)
from src.blender_sim.conveyor_demo.roller_motion import setup_rollers_from_config
from src.blender_sim.conveyor_demo.spawn import compute_spawn_frames, spawn_location_for_frame

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _add_fruit_rb(obj: bpy.types.Object, cfg: Dict[str, Any]) -> None:
    ld = cfg.get("fruit_linear_damping")
    ad = cfg.get("fruit_angular_damping")
    linear_damping = float(ld) if ld is not None else None
    angular_damping = float(ad) if ad is not None else None
    fk = (cfg.get("fruit_kind") or "sphere").lower()
    if fk in ("glb_citrus", "glb", "citrus_glb"):
        phys.add_active_convex_rb(
            obj,
            float(cfg.get("fruit_mass_kg", 0.12)),
            float(cfg.get("fruit_friction", cfg.get("sphere_friction", 0.78))),
            float(cfg.get("fruit_restitution", cfg.get("sphere_restitution", 0.06))),
            linear_damping=linear_damping,
            angular_damping=angular_damping,
        )
    else:
        phys.add_active_sphere_rb(
            obj,
            float(cfg.get("sphere_mass_kg", 0.12)),
            float(cfg.get("sphere_friction", 0.78)),
            float(cfg.get("sphere_restitution", 0.06)),
            linear_damping=linear_damping,
            angular_damping=angular_damping,
        )


def run_demo(raw_cfg: Dict[str, Any]) -> None:
    cfg = defaults.merge_config(raw_cfg)
    out_dir = Path(cfg["output_dir"]).resolve()
    renders_dir = out_dir / cfg.get("renders_subdir", "_tmp_frames")
    renders_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(int(cfg.get("seed", 42)))
    episode = int(cfg["episode_frame_count"])
    fps = int(cfg["render_fps"])

    fk = (cfg.get("fruit_kind") or "sphere").lower()
    glb_sequence: List[str] = []
    if fk in ("glb_citrus", "glb", "citrus_glb"):
        glb_sequence = build_citrus_glb_sequence(cfg, PROJECT_ROOT)
        if not glb_sequence:
            raise RuntimeError("citrus_glb_paths 비어 있음 — defaults 또는 JSON 확인")
        n_spawn = len(glb_sequence)
    else:
        n_spawn = int(cfg.get("sphere_count", 30))

    _clear_scene()
    scene = bpy.context.scene
    scene.gravity = (0.0, 0.0, -9.81)

    scene.render.resolution_x = int(cfg["render_width"])
    scene.render.resolution_y = int(cfg["render_height"])
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = episode
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.use_motion_blur = False

    eng = str(cfg.get("render_engine", "CYCLES")).upper()
    if eng == "CYCLES" and hasattr(scene.render, "engine"):
        scene.render.engine = "CYCLES"
        if hasattr(scene, "cycles"):
            configure_cycles_device(scene, cfg)
            scene.cycles.samples = int(cfg.get("cycles_samples", 28))
            scene.cycles.use_adaptive_sampling = True
    elif hasattr(scene.render, "engine"):
        scene.render.engine = "BLENDER_EEVEE_NEXT" if "EEVEE" in eng else eng

    if hasattr(scene, "view_settings"):
        scene.view_settings.exposure = float(cfg.get("view_exposure", 0.35))

    setup_world_background(scene, strength=float(cfg.get("world_bg_strength", 0.4)))

    sps = cfg.get("rigidbody_steps_per_second")
    phys.configure_rigidbody_world(
        scene,
        fps,
        int(cfg.get("physics_solver_iterations", 22)),
        steps_per_second=int(sps) if sps is not None else None,
    )

    build = build_conveyor(scene, cfg)
    belt_min, belt_max = build.belt_bounds
    spawn_min, spawn_max = build.spawn_bounds

    for so in build.static_objects:
        phys.add_passive_rb(
            so,
            friction=float(cfg.get("conveyor_friction", 0.82)),
            collision_shape="MESH",
            kinematic=False,
        )

    setup_rollers_from_config(scene, build.roller_objects, cfg)

    center = (belt_min + belt_max) * 0.5
    cam_style = (cfg.get("camera_style") or "diagonal").lower()
    if cam_style == "diagonal":
        setup_diagonal_camera(
            scene,
            look_at=center,
            belt_length=float(cfg["belt_length_m"]),
            belt_width=float(cfg["belt_width_m"]),
            lens_mm=float(cfg.get("camera_lens_mm", 40.0)),
        )
    else:
        setup_top_down_camera(
            scene,
            look_at=center,
            belt_length=float(cfg["belt_length_m"]),
            belt_width=float(cfg["belt_width_m"]),
            ortho_scale_factor=float(cfg.get("camera_ortho_scale_factor", 1.15)),
            height_m=float(cfg.get("camera_height_m", 7.0)),
        )
    setup_factory_lights(scene, center, float(cfg["belt_length_m"]), float(cfg["belt_width_m"]))

    spawn_frames = compute_spawn_frames(n_spawn, episode, cfg)
    fruit_objs: List[bpy.types.Object] = []
    spawn_idx = 0

    glb_templates: Dict[str, bpy.types.Object] = {}
    use_cache = bool(cfg.get("use_glb_instance_cache", True))
    if fk in ("glb_citrus", "glb", "citrus_glb") and glb_sequence and use_cache:
        for rel in dict.fromkeys(glb_sequence):
            glb_templates[rel] = build_glb_template(rel, PROJECT_ROOT, cfg)

    meta_path = out_dir / cfg.get("metadata_filename", "conveyor_demo_meta.jsonl")
    meta_lines: List[str] = []
    write_meta = bool(cfg.get("write_metadata", False))

    skip_render = bool(cfg.get("skip_render", False))

    for frame in range(1, episode + 1):
        while spawn_idx < len(spawn_frames) and spawn_frames[spawn_idx] == frame:
            loc = spawn_location_for_frame(cfg, spawn_min, spawn_max, rng)
            gpath = glb_sequence[spawn_idx] if glb_sequence else None
            tpl = glb_templates.get(gpath) if gpath and glb_templates else None
            obj = create_fruit_object(
                spawn_idx,
                loc,
                cfg,
                project_root=PROJECT_ROOT,
                glb_path=gpath,
                glb_template=tpl,
            )
            _add_fruit_rb(obj, cfg)
            fruit_objs.append(obj)
            spawn_idx += 1

        scene.frame_set(frame)
        bpy.context.view_layer.update()
        if not skip_render:
            scene.render.filepath = str(renders_dir / f"frame_{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
        if write_meta:
            meta_lines.append(
                json.dumps(
                    {
                        "frame": frame,
                        "spawns_so_far": spawn_idx,
                        "fruit_count": len(fruit_objs),
                    },
                    ensure_ascii=False,
                )
            )

    if write_meta:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write("\n".join(meta_lines) + ("\n" if meta_lines else ""))

    blend_rel = cfg.get("save_blend_path")
    if blend_rel:
        blend_abs = (out_dir / str(blend_rel)).resolve()
        blend_abs.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_abs))
        print(f"[conveyor_demo] Saved .blend (Blender에서 열어 재생·뷰포트 확인) -> {blend_abs}")

    print(f"[conveyor_demo] Intermediate PNGs -> {renders_dir}")
    print(f"[conveyor_demo] Spawns completed: {spawn_idx} / {n_spawn}")
    if write_meta:
        print(f"[conveyor_demo] Meta -> {meta_path}")

