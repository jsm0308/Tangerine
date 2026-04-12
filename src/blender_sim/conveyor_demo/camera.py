"""월드 배경 + 카메라(탑다운 정사영 또는 대각선 투시)."""

from __future__ import annotations

import math

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


def setup_diagonal_camera(
    scene: bpy.types.Scene,
    *,
    look_at: Vector,
    belt_length: float,
    belt_width: float,
    lens_mm: float = 40.0,
) -> bpy.types.Object:
    """
    벨트 전체가 보이도록 약간 앞·옆·위(대각선)에서 투시.
    """
    span = max(belt_length, belt_width, 1.0)
    # 화면: 벨트 길이(X)가 가로로 보이도록 카메라를 -Y 쪽·위로 배치
    off_x = -span * 0.42
    off_y = -span * 1.05
    off_z = span * 0.92

    cam_data = bpy.data.cameras.new(name="DiagCam")
    cam_data.type = "PERSP"
    cam_data.lens = float(lens_mm)
    cam_data.clip_start = 0.05
    cam_data.clip_end = 500.0

    cam_obj = bpy.data.objects.new("DiagCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_obj.location = Vector((look_at.x + off_x, look_at.y + off_y, look_at.z + off_z))

    target = bpy.data.objects.new("CamLookAt", None)
    target.empty_display_size = 0.12
    target.location = look_at
    scene.collection.objects.link(target)

    con = cam_obj.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    return cam_obj


def setup_factory_lights(
    scene: bpy.types.Scene,
    center: Vector,
    belt_length: float,
    belt_width: float,
) -> None:
    """에어리어 + 태양광."""
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
