"""
컨베이어 전체 기울기(+X 방향으로 내리막).

월드 Y축 기준 회전(Blender 오일러 Y). 피벗 기본: 벨트 길이 방향 중앙 (X=L/2, Z=pivot_z).
`conveyor_pitch_deg` 가 0이면 아무 것도 하지 않고, build 시점의 바운딩을 그대로 반환.

물리: 리지드바디는 이 함수 호출 **이후**에 붙인다(월드 변환 확정 후).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

import bpy
from mathutils import Vector

from src.blender_sim.conveyor.conveyor_mesh import ConveyorBuildResult


def _world_aabb(objects: list[bpy.types.Object]) -> Tuple[Vector, Vector]:
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    bpy.context.view_layer.update()
    for obj in objects:
        for c in obj.bound_box:
            w = obj.matrix_world @ Vector(c)
            mn.x, mn.y, mn.z = min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)
            mx.x, mx.y, mx.z = max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)
    return mn, mx


def apply_conveyor_pitch(
    scene: bpy.types.Scene,
    build: ConveyorBuildResult,
    cfg: Dict[str, Any],
) -> Tuple[Vector, Vector, Vector, Vector]:
    """
    롤러·정적 메시를 ``ConveyorPitch`` Empty 자식으로 두고 Y축 회전 적용.

    Returns:
        (belt_min, belt_max, spawn_min, spawn_max) 월드 AABB
    """
    pitch_deg = float(cfg.get("conveyor_pitch_deg", 0.0))
    if abs(pitch_deg) < 1e-9:
        return (
            build.belt_bounds[0],
            build.belt_bounds[1],
            build.spawn_bounds[0],
            build.spawn_bounds[1],
        )

    L = float(cfg["belt_length_m"])
    px = cfg.get("conveyor_pitch_pivot_x_m")
    pivot_x = float(px) if px is not None else L * 0.5
    pivot_z = float(cfg.get("conveyor_pitch_pivot_z_m", 0.0))
    pitch_rad = math.radians(pitch_deg)

    empty = bpy.data.objects.new("ConveyorPitch", None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.35
    scene.collection.objects.link(empty)
    empty.location = (pivot_x, 0.0, pivot_z)
    empty.rotation_euler = (0.0, 0.0, 0.0)

    to_parent = list(build.roller_objects) + list(build.static_objects)
    bpy.ops.object.select_all(action="DESELECT")
    for o in to_parent:
        o.select_set(True)
    empty.select_set(True)
    bpy.context.view_layer.objects.active = empty
    bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

    empty.rotation_euler = (0.0, pitch_rad, 0.0)
    bpy.context.view_layer.update()

    belt_min, belt_max = _world_aabb(to_parent)
    spawn_min, spawn_max = _world_aabb(list(build.roller_objects))
    return belt_min, belt_max, spawn_min, spawn_max
