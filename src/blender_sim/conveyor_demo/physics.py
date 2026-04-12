"""리지드 바디 월드 및 오브젝트 등록 (Blender 버전 호환)."""

from __future__ import annotations

from typing import Any

import bpy


def ensure_rigidbody_world(scene: bpy.types.Scene) -> None:
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()


def configure_rigidbody_world(
    scene: bpy.types.Scene,
    fps: int,
    solver_iterations: int,
    *,
    steps_per_second: int | None = None,
) -> None:
    ensure_rigidbody_world(scene)
    rbw = scene.rigidbody_world
    if not rbw:
        return
    if hasattr(rbw, "steps_per_second"):
        sps = steps_per_second if steps_per_second is not None else max(120, fps * 4)
        rbw.steps_per_second = max(60, int(sps))
    elif hasattr(rbw, "substeps_per_frame"):
        rbw.substeps_per_frame = max(4, min(32, max(2, solver_iterations // 2)))
    if hasattr(rbw, "solver_iterations"):
        rbw.solver_iterations = max(15, solver_iterations)


def add_passive_rb(
    obj: bpy.types.Object,
    *,
    friction: float,
    collision_shape: str,
    kinematic: bool,
    restitution: float = 0.02,
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.rigid_body is None:
        bpy.ops.rigidbody.object_add(type="PASSIVE")
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = restitution
    obj.rigid_body.collision_shape = collision_shape
    if hasattr(obj.rigid_body, "kinematic"):
        obj.rigid_body.kinematic = kinematic


def add_active_sphere_rb(
    obj: bpy.types.Object,
    mass: float,
    friction: float,
    restitution: float,
    *,
    linear_damping: float | None = None,
    angular_damping: float | None = None,
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    obj.rigid_body.mass = mass
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = restitution
    obj.rigid_body.collision_shape = "SPHERE"
    rb = obj.rigid_body
    if rb is not None:
        if linear_damping is not None and hasattr(rb, "linear_damping"):
            rb.linear_damping = linear_damping
        if angular_damping is not None and hasattr(rb, "angular_damping"):
            rb.angular_damping = angular_damping


def add_active_convex_rb(
    obj: bpy.types.Object,
    mass: float,
    friction: float,
    restitution: float,
    *,
    linear_damping: float | None = None,
    angular_damping: float | None = None,
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    obj.rigid_body.mass = mass
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = restitution
    obj.rigid_body.collision_shape = "CONVEX_HULL"
    rb = obj.rigid_body
    if rb is not None:
        if linear_damping is not None and hasattr(rb, "linear_damping"):
            rb.linear_damping = linear_damping
        if angular_damping is not None and hasattr(rb, "angular_damping"):
            rb.angular_damping = angular_damping
