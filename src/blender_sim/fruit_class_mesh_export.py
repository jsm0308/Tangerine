"""
Blender: data/Fruits/ 아래 클래스 폴더별로 3D GLB 배치 (기본 15개 = 5클래스×3).

- 베이스: data/*.glb 중 최대 메시 1개 (순환)
- 형태: 크기·납작·경미 울퉁 (healthy_variants와 동일 계열)
- 재질: (1) 폴더 내 실제 이미지 1장 혼합 (2) 클래스별 정점 색 “병변 얼룩”
- UV: 구면 투영 우선 → 실패 시 스마트 언랩

glTF는 점 색(COLOR_0) + 이미지 텍스처 조합을 잘 내보냅니다.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

SIZE_LEVELS = (0.82, 1.0, 1.12)
OBLATE_LEVELS = (
    (1.06, 1.06, 0.88),
    (1.0, 1.0, 1.0),
    (0.94, 0.94, 1.08),
)
BUMP_STRENGTH = (0.0, 0.012, 0.022)


def _safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s.strip() or "unnamed"


def _norm_class(folder_name: str) -> str:
    return folder_name.strip().lower().replace(" ", "_")


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


def _decimate_if_needed(obj: bpy.types.Object, max_faces: int = 10000) -> None:
    """고폴리에서 정점색·UV가 과도하게 느려지므로 면 수 상한."""
    mesh = obj.data
    n = len(mesh.polygons)
    if n <= max_faces:
        return
    ratio = max(0.08, min(1.0, max_faces / float(n)))
    mod = obj.modifiers.new(name="FC_Decimate", type="DECIMATE")
    mod.ratio = ratio
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _apply_shape(obj: bpy.types.Object, size: float, oblate: Tuple[float, float, float]) -> None:
    sx, sy, sz = oblate
    obj.scale = (size * sx, size * sy, size * sz)
    bpy.ops.object.transform_apply(scale=True)


def _apply_bump(obj: bpy.types.Object, strength: float, seed: int) -> None:
    """서브디브 없이 가벼운 표면 노이즈만 (고폴리에서 멈춤 방지)."""
    if strength <= 1e-9:
        return
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    random.seed(seed)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.mesh.noise(factor=min(strength * 3.0, 0.08))
    except Exception:
        pass
    bpy.ops.object.mode_set(mode="OBJECT")


def _uv_sphere_or_smart(obj: bpy.types.Object) -> None:
    """sphere_project 는 고폴리에서 매우 느리거나 멈출 수 있어 smart_project 만 사용."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(66.0),
            island_margin=0.02,
            correct_aspect=True,
            scale_to_bounds=True,
        )
    except Exception:
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def _vertex_paint_disease(obj: bpy.types.Object, class_norm: str, seed: int) -> None:
    """클래스별 과피 베이스 + 반점 색을 루프에 기록 (glTF COLOR_0)."""
    mesh = obj.data
    rng = random.Random(seed)

    while len(mesh.vertex_colors) > 0:
        mesh.vertex_colors.remove(mesh.vertex_colors[0])
    vcol = mesh.vertex_colors.new(name="DiseaseMask")

    # 베이스 껍질 RGBA
    def peel_base() -> Tuple[float, float, float, float]:
        return (0.92 + rng.uniform(-0.04, 0.04), 0.48 + rng.uniform(-0.06, 0.06), 0.14 + rng.uniform(-0.03, 0.03), 1.0)

    def spot_canker() -> Tuple[float, float, float, float]:
        return (0.72 + rng.uniform(0, 0.08), 0.52 + rng.uniform(0, 0.1), 0.08, 1.0)

    def spot_scab() -> Tuple[float, float, float, float]:
        return (0.82, 0.62, 0.38, 1.0)

    def spot_black() -> Tuple[float, float, float, float]:
        return (0.18 + rng.uniform(0, 0.1), 0.08, 0.06, 1.0)

    def spot_greening() -> Tuple[float, float, float, float]:
        return (0.45 + rng.uniform(0, 0.15), 0.65 + rng.uniform(-0.1, 0.1), 0.22, 1.0)

    for poly in mesh.polygons:
        for li in poly.loop_indices:
            u = rng.random()
            base = peel_base()
            c = base
            if "healthy" in class_norm or class_norm in ("normal", "정상"):
                c = base
            elif "canker" in class_norm or "궤양" in class_norm:
                if u > 0.88:
                    c = spot_canker()
                elif u > 0.82:
                    c = (0.95, 0.85, 0.2, 1.0)  # halo
                else:
                    c = base
            elif "scab" in class_norm or "총채" in class_norm:
                if u > 0.90:
                    c = spot_scab()
                elif u > 0.84:
                    c = (0.88, 0.72, 0.5, 1.0)
                else:
                    c = base
            elif "black" in class_norm or "spot" in class_norm:
                if u > 0.91:
                    c = spot_black()
                elif u > 0.86:
                    c = (0.55, 0.15, 0.1, 1.0)  # brick margin
                else:
                    c = base
            elif "green" in class_norm or "greening" in class_norm:
                if u > 0.75:
                    c = spot_greening()
                else:
                    c = base
            else:
                if u > 0.9:
                    c = (0.7, 0.45, 0.15, 1.0)
                else:
                    c = base
            vcol.data[li].color = c


def _build_material_export_safe(
    mat_name: str,
    image: Optional[bpy.types.Image],
    vertex_color_attr: str,
) -> bpy.types.Material:
    """Principled + (선택) 이미지 + 점색 — glTF 호환 위주."""
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")

    try:
        vcol_node = nodes.new("ShaderNodeVertexColor")
        if hasattr(vcol_node, "layer_name"):
            vcol_node.layer_name = vertex_color_attr
        vc_out = vcol_node.outputs.get("Color") or list(vcol_node.outputs)[0]
    except Exception:
        attr = nodes.new("ShaderNodeAttribute")
        attr.attribute_name = vertex_color_attr
        vc_out = attr.outputs["Color"]

    if image:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Smart"
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MIX"
        mix.inputs["Fac"].default_value = 0.42
        links.new(tex.outputs["Color"], mix.inputs["Color1"])
        links.new(vc_out, mix.inputs["Color2"])
        links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        links.new(vc_out, bsdf.inputs["Base Color"])

    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.48
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

    return mat


def _export_glb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(path.resolve()),
            export_format="GLB",
            use_selection=False,
            export_yup=True,
        )
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=str(path.resolve()), export_format="GLB")


def _list_class_images(class_dir: Path) -> List[Path]:
    if not class_dir.is_dir():
        return []
    out: List[Path] = []
    for p in sorted(class_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in IMAGE_EXT:
            out.append(p)
    return out


def run_fruit_class_mesh_export(cfg: Dict[str, Any]) -> None:
    fruits_root = Path(cfg["fruits_root"]).resolve()
    mesh_paths = [Path(p).resolve() for p in cfg.get("mesh_paths") or []]
    output_root = Path(cfg["output_root"]).resolve()
    total_target = int(cfg.get("total_exports", 15))
    resume = bool(cfg.get("resume", False))

    if not mesh_paths:
        print("[fruit_class] mesh_paths empty")
        return

    class_dirs = sorted(
        [p for p in fruits_root.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    )
    if not class_dirs:
        print(f"[fruit_class] No class folders under {fruits_root}")
        return

    n_cls = len(class_dirs)
    base = total_target // n_cls
    extra = total_target % n_cls
    counts = [base + (1 if i < extra else 0) for i in range(n_cls)]
    print(
        f"[fruit_class] {n_cls} classes, counts={counts} (total {sum(counts)}) → {output_root}"
    )

    variant_idx = 0
    done = skipped = failed = 0

    for ci, class_dir in enumerate(class_dirs):
        class_name = class_dir.name
        class_norm = _norm_class(class_name)
        imgs = _list_class_images(class_dir)
        out_sub = output_root / _safe_name(class_name)
        out_sub.mkdir(parents=True, exist_ok=True)
        per_class = counts[ci]

        for local_i in range(per_class):
            mi = variant_idx % len(mesh_paths)
            mesh_path = mesh_paths[mi]
            si = variant_idx % len(SIZE_LEVELS)
            oi = (variant_idx // 3) % len(OBLATE_LEVELS)
            bi = (variant_idx // 2) % len(BUMP_STRENGTH)
            size = SIZE_LEVELS[si]
            obl = OBLATE_LEVELS[oi]
            bump = BUMP_STRENGTH[bi]

            seed = int.from_bytes(
                hashlib.md5(f"{class_name}-{local_i}-{variant_idx}".encode()).digest()[:4],
                "little",
            )
            stem = _safe_name(mesh_path.stem)
            out_file = out_sub / f"{stem}__v{local_i:02d}_s{si}_o{oi}_b{bi}.glb"

            if resume and out_file.is_file() and out_file.stat().st_size > 0:
                skipped += 1
                variant_idx += 1
                continue

            print(f"[fruit_class] {class_name} / {out_file.name}", flush=True)

            img_path: Optional[Path] = None
            if imgs:
                img_path = imgs[local_i % len(imgs)]

            try:
                _clear_scene_objects()
                obj = _import_main_mesh(mesh_path)
                _apply_shape(obj, size, obl)
                _apply_bump(obj, bump, seed)
                _decimate_if_needed(obj, max_faces=10000)
                _uv_sphere_or_smart(obj)
                _vertex_paint_disease(obj, class_norm, seed)

                img_block: Optional[bpy.types.Image] = None
                if img_path is not None:
                    try:
                        img_block = bpy.data.images.load(str(img_path), check_existing=False)
                        img_block.colorspace_settings.name = "sRGB"
                    except Exception:
                        img_block = None

                mat = _build_material_export_safe(
                    f"Mat_{_safe_name(class_name)}_{local_i}",
                    img_block,
                    "DiseaseMask",
                )
                obj.data.materials.clear()
                obj.data.materials.append(mat)

                _export_glb(out_file)

                if img_block:
                    try:
                        bpy.data.images.remove(img_block, do_unlink=True)
                    except Exception:
                        pass
                done += 1
            except Exception as e:
                print(f"[fruit_class] Fail {out_file.name}: {e}")
                failed += 1

            variant_idx += 1

    print(f"[fruit_class] Done. {done} written, {skipped} skipped, {failed} failed")
