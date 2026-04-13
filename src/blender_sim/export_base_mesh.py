# Blender 전용: configs → job JSON 으로 받아 단일·단순 프리미티브 GLB만 내보냄 (꼭지 없음).
# 실행은 scripts/build_base_mesh.py 가 담당.

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blk in list(bpy.data.meshes):
        bpy.data.meshes.remove(blk)
    for blk in list(bpy.data.materials):
        bpy.data.materials.remove(blk)


def _add_primitive(spec: dict, defaults: dict) -> bpy.types.Object:
    kind = (spec.get("primitive") or defaults.get("primitive") or "icosphere").lower()
    radius = float(spec.get("radius", defaults.get("radius", 1.0)))
    loc = Vector(spec.get("location", [0.0, 0.0, 0.0]))

    if kind == "icosphere":
        subdiv = int(spec.get("subdivisions", defaults.get("subdivisions", 3)))
        subdiv = max(1, min(10, subdiv))
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=subdiv,
            radius=radius,
            enter_editmode=False,
            align="WORLD",
            location=tuple(loc),
        )
    elif kind == "cube":
        size = float(spec.get("size", defaults.get("size", 1.0)))
        bpy.ops.mesh.primitive_cube_add(
            size=size,
            location=tuple(loc),
        )
    elif kind == "uv_sphere":
        seg = int(spec.get("segments", 32))
        ring = int(spec.get("ring_count", 16))
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=radius,
            segments=seg,
            ring_count=ring,
            location=tuple(loc),
        )
    else:
        raise ValueError(f"Unknown primitive: {kind}")

    obj = bpy.context.active_object
    sc = spec.get("scale", [1.0, 1.0, 1.0])
    if len(sc) == 3:
        obj.scale = (float(sc[0]), float(sc[1]), float(sc[2]))
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    _ensure_smart_uv(obj)
    return obj


def _ensure_smart_uv(obj: bpy.types.Object) -> None:
    """glTF 알베도 매핑용 — 아이코스피어 등에 UV 레이어가 없으면 생성 후 Smart Project."""
    mesh = obj.data
    if mesh.uv_layers.active is None:
        mesh.uv_layers.new(name="UVMap")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def _orange_material(name: str, mat_cfg: dict):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bc = mat_cfg.get("base_color", [0.9, 0.42, 0.12, 1.0])
        bsdf.inputs["Base Color"].default_value = tuple(bc)
        bsdf.inputs["Roughness"].default_value = float(mat_cfg.get("roughness", 0.55))
        sil = "Specular IOR Level"
        if sil in bsdf.inputs:
            bsdf.inputs[sil].default_value = float(mat_cfg.get("specular_ior_level", 0.35))
    return mat


def _export_one(out_path: Path, obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.export_scene.gltf(
        filepath=str(out_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_materials="EXPORT",
    )


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) < 1:
        print("Usage: blender --background --python ... -- --job-json PATH", file=sys.stderr)
        sys.exit(1)
    job_path = Path(argv[0]).resolve()
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)

    defaults = job.get("defaults") or {}
    mat_cfg = job.get("material") or {}

    for exp in job.get("exports") or []:
        _clear_scene()
        name = exp.get("asset_name") or "Fruit"
        obj = _add_primitive(exp, defaults)
        obj.name = name
        mat = _orange_material(f"{name}_Mat", mat_cfg)
        out = Path(exp["out_path"])
        _export_one(out, obj, mat)
        print(f"[export_base_mesh] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
