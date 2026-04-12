"""
5m 롤러 컨베이어 프로시저 메시: 아워글래스 롤러, 데크, 알루미늄 레일, 측면 체인, 단자 모터 하우징.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import bmesh
import bpy
from mathutils import Vector

from src.blender_sim.conveyor_demo import materials as matlib


@dataclass
class ConveyorBuildResult:
    roller_objects: List[bpy.types.Object]
    static_objects: List[bpy.types.Object]
    belt_bounds: Tuple[Vector, Vector]  # min, max world (모터·체인 포함 — 카메라 등용)
    spawn_bounds: Tuple[Vector, Vector]  # 롤러 베드만 — 과일 스폰·높이용


def _hourglass_roller_mesh(
    name: str,
    r_end: float,
    r_center: float,
    length: float,
    n_around: int = 26,
    n_along: int = 10,
) -> bpy.types.Mesh:
    bm = bmesh.new()
    half = length * 0.5
    rings: List[List[Any]] = []
    for ai in range(n_along):
        t = ai / (n_along - 1) if n_along > 1 else 0.5
        y = half * (2 * t - 1)
        tt = y / half if abs(half) > 1e-9 else 0.0
        r = r_end - (r_end - r_center) * (math.cos(math.pi * tt * 0.5) ** 2)
        ring = []
        for bi in range(n_around):
            ang = 2 * math.pi * bi / n_around
            x = r * math.cos(ang)
            z = r * math.sin(ang)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for ai in range(n_along - 1):
        for bi in range(n_around):
            b2 = (bi + 1) % n_around
            v00 = rings[ai][bi]
            v01 = rings[ai][b2]
            v10 = rings[ai + 1][bi]
            v11 = rings[ai + 1][b2]
            try:
                bm.faces.new((v00, v01, v11, v10))
            except ValueError:
                bm.faces.new((v00, v10, v11, v01))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    mesh.validate(verbose=False)
    return mesh


def _new_cube_object(
    name: str,
    sx: float,
    sy: float,
    sz: float,
    loc: Tuple[float, float, float],
    mat: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx / 2, sy / 2, sz / 2)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj


def _add_end_basket(
    static_parts: List[bpy.types.Object],
    L: float,
    W: float,
    deck_z: float,
    r_end: float,
    mat: bpy.types.Material,
    cfg: Dict[str, Any],
) -> None:
    """벨트 +X 끝 수집 바구니(벽+바닥, 인입측은 개방)."""
    if not bool(cfg.get("end_basket_enabled", True)):
        return
    depth = float(cfg.get("end_basket_depth_m", 0.36))
    inner_w = float(cfg.get("end_basket_inner_width_m", min(W * 0.88, 0.46)))
    wall_t = float(cfg.get("end_basket_wall_thickness_m", 0.018))
    wall_h = float(cfg.get("end_basket_wall_height_m", 0.14))
    # 바닥 상면이 롤러 아래쪽이면 떨어진 귤이 안으로 빠짐
    floor_top_z = float(cfg.get("end_basket_floor_top_z_m", deck_z - 0.06))
    floor_th = float(cfg.get("end_basket_floor_thickness_m", 0.022))
    floor_z = floor_top_z - floor_th * 0.5
    # 벨트 끝(L 근처)에서 +X로 깊이
    cx = L + depth * 0.5 + float(cfg.get("end_basket_x_extra_m", 0.02))

    static_parts.append(
        _new_cube_object(
            "BasketFloor",
            depth,
            inner_w,
            floor_th,
            (cx, 0.0, floor_z),
            mat,
        )
    )
    # 좌우 벽 (Y)
    wy = inner_w * 0.5 + wall_t * 0.5
    for side, sy in (("L", wy), ("R", -wy)):
        static_parts.append(
            _new_cube_object(
                f"BasketWallY_{side}",
                depth - wall_t * 2,
                wall_t,
                wall_h,
                (cx, sy, floor_top_z + wall_h * 0.5),
                mat,
            )
        )
    # 뒤벽 (+X)
    bx = cx + depth * 0.5 - wall_t * 0.5
    static_parts.append(
        _new_cube_object(
            "BasketWallBack",
            wall_t,
            inner_w + wall_t * 2,
            wall_h,
            (bx, 0.0, floor_top_z + wall_h * 0.5),
            mat,
        )
    )


def _add_conveyor_legs(
    static_parts: List[bpy.types.Object],
    L: float,
    W: float,
    deck_z: float,
    mat_alu: bpy.types.Material,
    cfg: Dict[str, Any],
) -> None:
    """데크 아래 지지각(다리) — 롤러 베드와 동일 X 범위를 따라 배치."""
    H = float(cfg.get("conveyor_leg_height_m", 0.74))
    t = float(cfg.get("conveyor_leg_thickness_m", 0.055))
    n_pairs = max(2, int(cfg.get("conveyor_leg_pairs_along_belt", 3)))
    _yo = cfg.get("conveyor_leg_y_offset_from_center_m")
    y_off = float(_yo) if _yo is not None else W * 0.38
    # 덱 하단 근처(z≈0)에서 바닥(z≈-H)까지
    z_center = -H * 0.5
    for i in range(n_pairs):
        u = (i + 0.5) / n_pairs
        x = 0.08 + (L - 0.16) * u
        for sy in (-1.0, 1.0):
            static_parts.append(
                _new_cube_object(
                    f"Leg_{i:02d}_{'L' if sy > 0 else 'R'}",
                    t,
                    t,
                    H,
                    (x, sy * y_off, z_center),
                    mat_alu,
                )
            )


def _merge_static(objects: List[bpy.types.Object], name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    merged = bpy.context.active_object
    merged.name = name
    return merged


def build_conveyor(scene: bpy.types.Scene, cfg: Dict[str, Any]) -> ConveyorBuildResult:
    L = float(cfg["belt_length_m"])
    W = float(cfg["belt_width_m"])
    n_roll = max(8, int(cfg["roller_count"]))
    r_end = float(cfg["roller_end_radius_m"])
    r_cen = float(cfg["roller_center_radius_m"])

    mat_rubber = matlib.make_rubber_roller_material()
    mat_alu = matlib.make_brushed_aluminum()
    mat_chain = matlib.make_chain_steel()
    mat_deck = matlib.make_deck_steel()

    roller_mesh = _hourglass_roller_mesh("RollerHourglassMesh", r_end, r_cen, W, 26, 10)

    rollers: List[bpy.types.Object] = []
    pitch = L / n_roll
    for i in range(n_roll):
        x = (i + 0.5) * pitch
        dup = bpy.data.objects.new(f"Roller_{i:03d}", roller_mesh)
        scene.collection.objects.link(dup)
        dup.location = (x, 0.0, r_end)
        dup.data.materials.append(mat_rubber)
        rollers.append(dup)

    deck_z = 0.012
    static_parts: List[bpy.types.Object] = []
    static_parts.append(
        _new_cube_object(
            "DeckPlate",
            L + 0.08,
            W + 0.04,
            0.024,
            (L * 0.5, 0.0, deck_z),
            mat_deck,
        )
    )

    rail_h = float(cfg.get("side_rail_height_m", 0.135))
    rail_th = float(cfg.get("side_rail_thickness_m", 0.022))
    rail_y = W * 0.5 - rail_th * 0.5 - 0.002
    for side, sy in (("L", rail_y), ("R", -rail_y)):
        static_parts.append(
            _new_cube_object(
                f"SideRail_{side}",
                L + 0.1,
                rail_th,
                rail_h,
                (L * 0.5, sy, deck_z + 0.012 + rail_h * 0.5),
                mat_alu,
            )
        )

    # 모터 하우징 (인입단 -X)
    static_parts.append(
        _new_cube_object(
            "MotorHousing",
            0.42,
            W * 0.92,
            0.26,
            (-0.18, 0.0, deck_z + 0.13),
            mat_alu,
        )
    )
    bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=0.34, location=(-0.2, 0.0, deck_z + 0.14))
    cyl = bpy.context.active_object
    cyl.name = "MotorShaftCover"
    cyl.rotation_euler = (0.0, math.radians(90), 0.0)
    cyl.data.materials.append(mat_alu)
    static_parts.append(cyl)

    # 체인 링크 (측면) — 레일 바깥으로 약간 벌림
    chain_objs: List[bpy.types.Object] = []
    n_links = max(6, int(L / 0.22))
    edge_y = float(cfg.get("chain_edge_offset_from_center_m", max(abs(rail_y) + 0.036, W * 0.5 + 0.028)))
    chain_z = deck_z + r_end * 0.85
    for side_mul in (-1.0, 1.0):
        y0 = edge_y * side_mul
        for j in range(n_links):
            x = 0.15 + (L - 0.3) * (j + 0.5) / n_links
            bpy.ops.mesh.primitive_torus_add(
                major_radius=0.02,
                minor_radius=0.0055,
                major_segments=10,
                minor_segments=6,
                location=(x, y0, chain_z),
            )
            t = bpy.context.active_object
            t.name = f"Chain_{side_mul:+.0f}_{j:02d}"
            t.rotation_euler = (math.radians(90), 0.0, math.radians(25))
            t.data.materials.append(mat_chain)
            chain_objs.append(t)

    static_parts.extend(chain_objs)
    _add_end_basket(static_parts, L, W, deck_z, r_end, mat_deck, cfg)
    _add_conveyor_legs(static_parts, L, W, deck_z, mat_alu, cfg)
    merged_static = _merge_static(static_parts, "ConveyorStatic")

    bpy.context.view_layer.update()
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for obj in rollers + [merged_static]:
        for c in obj.bound_box:
            w = obj.matrix_world @ Vector(c)
            mn.x, mn.y, mn.z = min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)
            mx.x, mx.y, mx.z = max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)

    # 스폰은 롤러 베드만 사용 (모터가 X 음수로 나가 전체 바운드가 밀려 스폰이 벨트 옆으로 감)
    smn = Vector((1e9, 1e9, 1e9))
    smx = Vector((-1e9, -1e9, -1e9))
    for obj in rollers:
        for c in obj.bound_box:
            w = obj.matrix_world @ Vector(c)
            smn.x, smn.y, smn.z = min(smn.x, w.x), min(smn.y, w.y), min(smn.z, w.z)
            smx.x, smx.y, smx.z = max(smx.x, w.x), max(smx.y, w.y), max(smx.z, w.z)

    return ConveyorBuildResult(
        roller_objects=rollers,
        static_objects=[merged_static],
        belt_bounds=(mn, mx),
        spawn_bounds=(smn, smx),
    )
