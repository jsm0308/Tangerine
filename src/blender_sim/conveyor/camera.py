"""월드 배경 + 카메라(탑다운 정사영 또는 대각선 투시) + 공장형 조명."""

from __future__ import annotations

import math
from typing import Any, Mapping, Tuple

import bpy
from mathutils import Vector


def setup_world_background(scene: bpy.types.Scene, *, strength: float = 0.35) -> None:
    """완전 검정 방지용 은은한 회색 배경."""
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()
    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.08, 0.08, 0.09, 1.0)
    bg.inputs["Strength"].default_value = strength
    out = nodes.new("ShaderNodeOutputWorld")
    links.new(bg.outputs["Background"], out.inputs["Surface"])


def setup_top_down_camera(
    scene: bpy.types.Scene,
    *,
    look_at: Vector,
    belt_length: float,
    belt_width: float,
    ortho_scale_factor: float,
    height_m: float,
) -> bpy.types.Object:
    """벨트 중심 위 정사영 탑뷰 (Track To)."""
    cam_data = bpy.data.cameras.new(name="TopDownCam")
    cam_data.type = "ORTHO"
    span = max(belt_length, belt_width) * ortho_scale_factor
    cam_data.ortho_scale = max(span, 0.5)
    cam_data.clip_start = 0.05
    cam_data.clip_end = 500.0

    cam_obj = bpy.data.objects.new("TopDownCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_obj.location = Vector((look_at.x, look_at.y, look_at.z + height_m))

    target = bpy.data.objects.new("CamLookAt", None)
    target.empty_display_size = 0.15
    target.location = look_at
    scene.collection.objects.link(target)

    con = cam_obj.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    return cam_obj


def _as_offset_triplet(raw: Any, default: Tuple[float, float, float]) -> Tuple[float, float, float]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    return default


def _perspective_track_camera(
    scene: bpy.types.Scene,
    *,
    look_at: Vector,
    belt_length: float,
    belt_width: float,
    lens_mm: float,
    offset_factors: Tuple[float, float, float],
    cam_name: str,
) -> bpy.types.Object:
    """벨트 중심 기준 (-span*fx, -span*fy, +span*fz) 위치에서 Track To."""
    span = max(belt_length, belt_width, 1.0)
    fx, fy, fz = offset_factors
    off_x = -span * fx
    off_y = -span * fy
    off_z = span * fz

    cam_data = bpy.data.cameras.new(name=cam_name)
    cam_data.type = "PERSP"
    cam_data.lens = float(lens_mm)
    cam_data.clip_start = 0.05
    cam_data.clip_end = 500.0

    cam_obj = bpy.data.objects.new(cam_name, cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_obj.location = Vector((look_at.x + off_x, look_at.y + off_y, look_at.z + off_z))

    target = bpy.data.objects.new(f"{cam_name}_LookAt", None)
    target.empty_display_size = 0.12
    target.location = look_at
    scene.collection.objects.link(target)

    con = cam_obj.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    return cam_obj


def setup_diagonal_camera(
    scene: bpy.types.Scene,
    *,
    look_at: Vector,
    belt_length: float,
    belt_width: float,
    lens_mm: float = 40.0,
    cfg: Mapping[str, Any] | None = None,
) -> bpy.types.Object:
    """
    벨트 전체가 보이도록 약간 앞·옆·위(대각선)에서 투시.
    오프셋은 `camera_diagonal_offset_factors` [fx,fy,fz] 로 조정 (양수, span 배율).
    """
    cfg = cfg or {}
    fac = _as_offset_triplet(
        cfg.get("camera_diagonal_offset_factors"),
        (0.42, 1.05, 0.92),
    )
    return _perspective_track_camera(
        scene,
        look_at=look_at,
        belt_length=belt_length,
        belt_width=belt_width,
        lens_mm=lens_mm,
        offset_factors=fac,
        cam_name="DiagCam",
    )


def setup_line_inspection_camera(
    scene: bpy.types.Scene,
    *,
    look_at: Vector,
    belt_length: float,
    belt_width: float,
    lens_mm: float = 35.0,
    cfg: Mapping[str, Any] | None = None,
) -> bpy.types.Object:
    """
    라인 검사 카메라에 가깝게: 더 옆·낮게(벨트 측면 QC 뷰).
    `camera_line_inspection_offset_factors` 로 미세 조정.
    """
    cfg = cfg or {}
    fac = _as_offset_triplet(
        cfg.get("camera_line_inspection_offset_factors"),
        (0.28, 1.28, 0.55),
    )
    return _perspective_track_camera(
        scene,
        look_at=look_at,
        belt_length=belt_length,
        belt_width=belt_width,
        lens_mm=float(cfg.get("camera_line_inspection_lens_mm", lens_mm)),
        offset_factors=fac,
        cam_name="LineInspectionCam",
    )


def _setup_classic_factory_lights(
    scene: bpy.types.Scene,
    center: Vector,
    belt_length: float,
    belt_width: float,
) -> None:
    """기존: 태양 + 대형 에어리어 2기."""
    span = max(belt_length, belt_width, 1.0)

    sun_data = bpy.data.lights.new(name="SunMain", type="SUN")
    sun_data.energy = 2.5
    sun_data.angle = math.radians(0.5)
    sun_obj = bpy.data.objects.new("SunMain", sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.location = (center.x + span * 0.2, center.y - span * 0.3, center.z + span * 1.5)
    sun_obj.rotation_euler = (math.radians(55), math.radians(-25), math.radians(15))

    for i, (ex, ox, oy, oz, sx) in enumerate(
        (
            (4200.0, -span * 0.15, span * 0.05, span * 1.2, 0.5),
            (2200.0, span * 0.2, -span * 0.1, span * 0.95, 0.42),
        )
    ):
        ld = bpy.data.lights.new(name=f"FactoryArea_{i}", type="AREA")
        ld.energy = ex
        ld.size = span * sx
        lo = bpy.data.objects.new(ld.name, ld)
        scene.collection.objects.link(lo)
        lo.location = (center.x + ox, center.y + oy, center.z + oz)
        lo.rotation_euler = (math.radians(75 + i * 5), 0.0, math.radians(25 - i * 15))


def _setup_factory_bay_lights(
    scene: bpy.types.Scene,
    center: Vector,
    belt_length: float,
    belt_width: float,
    cfg: Mapping[str, Any],
) -> None:
    """공장 고베이 느낌: 약한 태양광 + 벨트 방향으로 나란한 천장 조명 + 측면 필."""
    span = max(belt_length, belt_width, 1.0)

    sun_energy = float(cfg.get("factory_sun_energy", 0.75))
    sun_angle = math.radians(float(cfg.get("factory_sun_angle_deg", 0.55)))
    sun_data = bpy.data.lights.new(name="SunSkylight", type="SUN")
    sun_data.energy = sun_energy
    sun_data.angle = sun_angle
    sun_obj = bpy.data.objects.new("SunSkylight", sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.location = (center.x + span * 0.15, center.y - span * 0.45, center.z + span * 1.65)
    sun_obj.rotation_euler = (math.radians(48), math.radians(-32), math.radians(12))

    n = max(2, int(cfg.get("factory_ceiling_light_count", 5)))
    energy_each = float(cfg.get("factory_ceiling_light_energy", 1600.0))
    ceiling_z = float(cfg.get("factory_ceiling_height_factor", 1.22)) * span
    sm_raw = cfg.get("factory_ceiling_light_size_m")
    size_m = float(sm_raw) if sm_raw is not None else max(0.08, span * 0.2)
    sy_raw = cfg.get("factory_ceiling_light_size_y_m")
    size_y_m = float(sy_raw) if sy_raw is not None else belt_width * 2.8
    cover = float(cfg.get("factory_ceiling_light_x_cover", 0.82))
    for i in range(n):
        t = (i + 0.5) / n
        x_off = (t - 0.5) * belt_length * cover
        ld = bpy.data.lights.new(name=f"CeilingBay_{i}", type="AREA")
        ld.energy = energy_each
        ld.shape = "RECTANGLE"
        ld.size = size_m
        ld.size_y = max(size_y_m, 0.05)
        lo = bpy.data.objects.new(ld.name, ld)
        scene.collection.objects.link(lo)
        lo.location = (center.x + x_off, center.y, center.z + ceiling_z)
        lo.rotation_euler = (0.0, 0.0, 0.0)

    fill = float(cfg.get("factory_side_fill_energy", 850.0))
    for i, ox in enumerate((-span * 0.42, span * 0.38)):
        ld = bpy.data.lights.new(name=f"SideFill_{i}", type="AREA")
        ld.energy = fill
        ld.size = span * 0.18
        lo = bpy.data.objects.new(ld.name, ld)
        scene.collection.objects.link(lo)
        lo.location = (center.x + ox, center.y + (-1 if i == 0 else 1) * span * 0.35, center.z + span * 0.55)
        lo.rotation_euler = (math.radians(68 + i * 6), 0.0, math.radians(-20 + i * 40))

    if bool(cfg.get("factory_spot_rig_enabled", False)):
        spot_e = float(cfg.get("factory_spot_energy", 420.0))
        spot_size = float(cfg.get("factory_spot_size", 0.35))
        for i, xo in enumerate((-belt_length * 0.22, belt_length * 0.18)):
            sd = bpy.data.lights.new(name=f"MachineVision_{i}", type="SPOT")
            sd.energy = spot_e
            sd.spot_size = math.radians(spot_size)
            so = bpy.data.objects.new(sd.name, sd)
            scene.collection.objects.link(so)
            so.location = (
                center.x + xo,
                center.y - span * 0.55,
                center.z + span * 0.45,
            )
            so.rotation_euler = (math.radians(72), 0.0, math.radians(8))


def setup_factory_lights(
    scene: bpy.types.Scene,
    center: Vector,
    belt_length: float,
    belt_width: float,
    cfg: Mapping[str, Any] | None = None,
) -> None:
    """
    조명 프리셋:
    - `factory_bay` (기본): 천장 스트립 + 측면 필 + 약한 태양광 (공장 실내에 가깝게).
    - `classic`: 기존 강한 에어리어 2 + 태양.
    """
    cfg = cfg or {}
    preset = (cfg.get("lighting_preset") or "factory_bay").lower().strip()
    if preset == "classic":
        _setup_classic_factory_lights(scene, center, belt_length, belt_width)
    else:
        _setup_factory_bay_lights(scene, center, belt_length, belt_width, cfg)
