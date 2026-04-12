"""
Blender 전용: data/ 베이스 GLB 3종 × 크기(3) × 납작(3) × 울퉁(3) = 81개 메시를
단일 텍스처(healthy 첫 이미지)로 입혀 GLB로 내보냅니다.

이후 단계: 이미지 수 × 81 조합은 별도 배치로 확장 가능(동일 형태 그리드).
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bpy

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

# 균일 크기 (정규화 후 추가 스케일)
SIZE_LEVELS: Tuple[float, ...] = (0.75, 1.0, 1.25)
# 납작/길쭉: (sx, sy, sz) — z 를 줄이면 위아래 납작
OBLATE_LEVELS: Tuple[Tuple[float, float, float], ...] = (
    (1.10, 1.10, 0.82),  # 납작
    (1.0, 1.0, 1.0),  # 중립
    (0.90, 0.90, 1.18),  # 세로로 약간 길쭉
)
# 울퉁불퉁: Displace 강도 (0 = 미적용). 메시 스케일 ~2BU 기준
BUMP_STRENGTH: Tuple[float, ...] = (0.0, 0.016, 0.034)


def _safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s.strip() or "unnamed"


def _clear_scene_objects() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _import_main_mesh(mesh_path: Path) -> bpy.types.Object:
    mesh_path = mesh_path.resolve()
    ext = mesh_path.suffix.lower()
    before = {o.name for o in bpy.context.scene.objects}

    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(mesh_path))
    elif ext == ".obj":
        try:
            bpy.ops.wm.obj_import(filepath=str(mesh_path))
        except AttributeError:
            bpy.ops.import_scene.obj(filepath=str(mesh_path))
    else:
        raise ValueError(f"Unsupported mesh format: {ext}")

    new_objs = [o for o in bpy.context.scene.objects if o.name not in before]
    meshes = [o for o in new_objs if o.type == "MESH"]
    if not meshes:
        for o in new_objs:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass
        raise RuntimeError(f"No MESH in imported file: {mesh_path}")

    obj = max(meshes, key=lambda o: len(o.data.vertices))
    for o in new_objs:
        if o != obj:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    dim = max(obj.dimensions) if max(obj.dimensions) > 1e-8 else 1.0
    s = 2.0 / dim
    obj.scale = (s, s, s)
    bpy.ops.object.transform_apply(scale=True)

    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.location = (0.0, 0.0, 0.0)

    bpy.ops.object.shade_smooth()
    obj.name = "Fruit_Subject"
    return obj


def _apply_shape_scale(obj: bpy.types.Object, size: float, oblate: Tuple[float, float, float]) -> None:
    sx, sy, sz = oblate
    obj.scale = (size * sx, size * sy, size * sz)
    bpy.ops.object.transform_apply(scale=True)


def _apply_bump_displace(obj: bpy.types.Object, strength: float, seed: int) -> None:
    if strength <= 1e-9:
        return
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 세부 지오메트리 확보
    sub = obj.modifiers.new(name="HV_Subdiv", type="SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub.name)

    tex = None
    try:
        tex = bpy.data.textures.new(f"HV_Bump_{seed}", type="CLOUDS")
        tex.noise_scale = 2.2 + (seed % 7) * 0.08
        tex.noise_depth = 2
    except Exception:
        try:
            tex = bpy.data.textures.new(f"HV_Bump_{seed}", type="MUSGRAVE")
        except Exception:
            tex = None

    if tex is not None:
        disp = obj.modifiers.new(name="HV_Displace", type="DISPLACE")
        disp.texture = tex
        disp.strength = strength
        disp.mid_level = 0.5
        try:
            bpy.ops.object.modifier_apply(modifier=disp.name)
            return
        except Exception:
            obj.modifiers.remove(disp)

    # 폴백: 정점 노이즈
    random.seed(seed)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.mesh.noise(factor=strength * 2.5)
    except Exception:
        pass
    bpy.ops.object.mode_set(mode="OBJECT")


def _smart_uv_unwrap(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(66.0),
            island_margin=0.004,
            area_weight=0.0,
            correct_aspect=True,
            scale_to_bounds=True,
        )
    except Exception:
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")


def _build_principled_material(tex_name: str, image: bpy.types.Image) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=tex_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Smart"

    tex.location = (-400, 0)
    bsdf.location = (0, 0)
    out_node.location = (300, 0)

    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.42
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.5
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.55
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
    return mat


def _export_glb(out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(out_file.resolve()),
            export_format="GLB",
            use_selection=False,
            export_yup=True,
        )
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=str(out_file.resolve()), export_format="GLB")


def run_healthy_variants_export(cfg: Dict[str, Any]) -> None:
    mesh_paths = [Path(p).resolve() for p in cfg.get("mesh_paths") or []]
    texture_path = Path(cfg["texture_path"]).resolve()
    output_root = Path(cfg["output_root"]).resolve()
    resume = bool(cfg.get("resume", False))

    if len(mesh_paths) != 3:
        print(f"[healthy_variants] Expected 3 mesh_paths, got {len(mesh_paths)}.")
        return

    if not texture_path.is_file():
        print(f"[healthy_variants] Missing texture: {texture_path}")
        return

    total = 3 * 3 * 3 * 3
    print(
        f"[healthy_variants] 3 bases × 3 size × 3 oblate × 3 bump = {total} GLBs → {output_root}"
    )

    try:
        img = bpy.data.images.load(str(texture_path), check_existing=False)
        img.colorspace_settings.name = "sRGB"
    except Exception as e:
        print(f"[healthy_variants] Failed to load texture: {e}")
        return

    done = 0
    skipped = 0
    failed = 0

    for bi, mesh_path in enumerate(mesh_paths):
        base_stem = _safe_name(mesh_path.stem)
        for si, sz in enumerate(SIZE_LEVELS):
            for oi, obl in enumerate(OBLATE_LEVELS):
                for bmi, bump in enumerate(BUMP_STRENGTH):
                    seed = 10000 + bi * 3000 + si * 300 + oi * 30 + bmi * 3
                    out_name = f"{base_stem}__s{si}_o{oi}_b{bmi}.glb"
                    out_file = output_root / out_name

                    if resume and out_file.is_file() and out_file.stat().st_size > 0:
                        skipped += 1
                        continue

                    try:
                        _clear_scene_objects()
                        obj = _import_main_mesh(mesh_path)
                        _apply_shape_scale(obj, sz, obl)
                        _apply_bump_displace(obj, bump, seed)
                        _smart_uv_unwrap(obj)

                        tex_name = f"Mat_{base_stem}_s{si}_o{oi}_b{bmi}"
                        mat = _build_principled_material(tex_name, img)
                        obj.data.materials.clear()
                        obj.data.materials.append(mat)

                        _export_glb(out_file)
                        done += 1
                    except Exception as e:
                        print(f"[healthy_variants] Fail {out_name}: {e}")
                        failed += 1

    try:
        bpy.data.images.remove(img, do_unlink=True)
    except Exception:
        pass

    print(
        f"[healthy_variants] Done. {done} written, {skipped} skipped, {failed} failed → {output_root}"
    )

