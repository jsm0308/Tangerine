"""
과일/제품 메시: GLB 임포트(주황 단색) 또는 UV 구 플레이스홀더.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any, Dict, List

import bpy
from mathutils import Vector


def _resolve_path(project_root: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_file():
        return p.resolve()
    cand = (project_root / rel_or_abs).resolve()
    return cand


def _tint_mesh_orange(obj: bpy.types.Object, name_suffix: str) -> None:
    mat = bpy.data.materials.new(name=f"OrangeCitrus_{name_suffix}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.96, 0.38, 0.08, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.48
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.45
    slots = getattr(obj.data, "materials", None)
    if slots is not None:
        slots.clear()
        slots.append(mat)


def _normalize_max_dimension(obj: bpy.types.Object, target_m: float) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    dims = obj.dimensions
    m = max(dims.x, dims.y, dims.z)
    if m > 1e-8:
        s = target_m / m
        obj.scale = (s, s, s)
        bpy.ops.object.transform_apply(scale=True)


def _import_join_normalize_tint(
    path: Path,
    cfg: Dict[str, Any],
    name: str,
    *,
    tint_suffix: str,
) -> bpy.types.Object:
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported: List[bpy.types.Object] = list(bpy.context.selected_objects)
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        for o in list(imported):
            bpy.data.objects.remove(o, do_unlink=True)
        raise RuntimeError(f"No mesh in GLB: {path}")

    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    if obj is None:
        obj = meshes[0]
    obj.name = name

    tgt = float(cfg.get("fruit_target_max_dim_m", 0.09))
    _normalize_max_dimension(obj, tgt)
    if not bool(cfg.get("preserve_glb_materials", False)):
        _tint_mesh_orange(obj, tint_suffix)
    return obj


def build_glb_template(glb_path: str, project_root: Path, cfg: Dict[str, Any]) -> bpy.types.Object:
    """GLB를 한 번만 임포트·스케일·머티리얼 적용한 뒤 숨긴 템플릿 오브젝트로 둔다."""
    path = _resolve_path(project_root, glb_path)
    if not path.is_file():
        raise FileNotFoundError(f"GLB not found: {path}")
    stem = path.stem.replace(".", "_")[:40]
    obj = _import_join_normalize_tint(path, cfg, f"Tpl_{stem}", tint_suffix=f"tpl_{stem}")
    obj.location = (0.0, 0.0, -999.0)
    obj.hide_viewport = True
    obj.hide_render = True
    return obj


def duplicate_fruit_from_template(
    template: bpy.types.Object,
    index: int,
    location: Vector,
    cfg: Dict[str, Any],
) -> bpy.types.Object:
    new_obj = template.copy()
    if new_obj.data is not None:
        new_obj.data = template.data.copy()
    new_obj.name = f"Fruit_{index:04d}"
    new_obj.hide_viewport = False
    new_obj.hide_render = False
    bpy.context.scene.collection.objects.link(new_obj)

    rng = random.Random(int(cfg.get("seed", 0)) + index * 7919)
    new_obj.rotation_euler = (
        rng.uniform(0, math.pi),
        rng.uniform(0, math.pi),
        rng.uniform(0, math.pi),
    )
    new_obj.location = location
    return new_obj


def import_citrus_glb(
    index: int,
    location: Vector,
    glb_path: str,
    project_root: Path,
    cfg: Dict[str, Any],
) -> bpy.types.Object:
    path = _resolve_path(project_root, glb_path)
    if not path.is_file():
        raise FileNotFoundError(f"GLB not found: {path}")

    obj = _import_join_normalize_tint(path, cfg, f"Fruit_{index:04d}", tint_suffix=f"{index:04d}")

    rng = random.Random(int(cfg.get("seed", 0)) + index * 7919)
    obj.rotation_euler = (
        rng.uniform(0, math.pi),
        rng.uniform(0, math.pi),
        rng.uniform(0, math.pi),
    )

    obj.location = location
    return obj


def create_fruit_object(
    index: int,
    location: Vector,
    cfg: Dict[str, Any],
    *,
    project_root: Path | None = None,
    glb_path: str | None = None,
    glb_template: bpy.types.Object | None = None,
) -> bpy.types.Object:
    kind = (cfg.get("fruit_kind") or "sphere").lower()
    if kind in ("glb_citrus", "glb", "citrus_glb"):
        if not glb_path:
            raise ValueError("glb_path required for glb_citrus")
        root = project_root or Path(".")
        if glb_template is not None:
            return duplicate_fruit_from_template(glb_template, index, location, cfg)
        return import_citrus_glb(index, location, glb_path, root, cfg)
    if kind == "sphere":
        return _uv_sphere(index, location, cfg)
    raise ValueError(f"Unknown fruit_kind: {kind}")


def _uv_sphere(index: int, location: Vector, cfg: Dict[str, Any]) -> bpy.types.Object:
    r = float(cfg.get("sphere_radius_m", 0.038))
    seg = max(8, int(cfg.get("sphere_uv_segments", 28)))
    rings = max(6, int(cfg.get("sphere_uv_rings", 18)))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=rings, location=location)
    obj = bpy.context.active_object
    obj.name = f"Fruit_{index:04d}"

    rng = random.Random(int(cfg.get("seed", 0)) + index * 7919)
    obj.rotation_euler = (
        rng.uniform(0, math.pi),
        rng.uniform(0, math.pi),
        rng.uniform(0, math.pi),
    )

    mat = bpy.data.materials.new(name=f"Mat_Fruit_{index:04d}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.92, 0.42, 0.08, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.52
    if obj.data.materials:
        obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def build_citrus_glb_sequence(cfg: Dict[str, Any], project_root: Path | None = None) -> List[str]:
    """
    스폰에 쓸 GLB 경로 목록 (프로젝트 루트 상대 문자열).

    - ``citrus_glb_directory`` 가 비어 있지 않으면: 해당 폴더 및 하위 폴더의 ``*.glb`` 중
      ``citrus_spawn_total`` 개까지 (기본 30), 셔플 옵션 적용.
    - 비어 있으면: ``citrus_glb_paths`` × ``fruit_per_mesh`` (기존 동작).
    """
    root = project_root.resolve() if project_root is not None else Path(".").resolve()
    d = (cfg.get("citrus_glb_directory") or "").strip()
    if d:
        dirp = (root / d).resolve()
        if dirp.is_dir():
            glbs = sorted(
                p
                for p in dirp.rglob("*.glb")
                if p.is_file()
                and not p.name.startswith("_")
                and not any(
                    part.startswith("_")
                    for part in p.relative_to(dirp).parts[:-1]
                )
            )
            if glbs:
                total = int(cfg.get("citrus_spawn_total", min(30, len(glbs))))
                total = max(1, min(total, len(glbs)))
                if cfg.get("shuffle_fruit_order", True):
                    rng = random.Random(int(cfg.get("seed", 42)))
                    rng.shuffle(glbs)
                picked = glbs[:total]
                return [str(p.relative_to(root)).replace("\\", "/") for p in picked]

    paths = list(cfg.get("citrus_glb_paths") or [])
    per = int(cfg.get("fruit_per_mesh", 10))
    seq: List[str] = []
    for p in paths:
        seq.extend([p] * per)
    if cfg.get("shuffle_fruit_order", True):
        rng = random.Random(int(cfg.get("seed", 42)))
        rng.shuffle(seq)
    return seq
