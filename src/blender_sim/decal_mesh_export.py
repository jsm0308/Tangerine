"""
Blender: 병변 패치(RGBA)를 UV 알베도에 스탬프(Texture Paint와 동일한 2D 텍스처 공간 합성).

- 베이스: mesh_paths 의 healthy GLB에 실린 알베도 이미지·UV를 우선 사용 (use_healthy_albedo_base)
- 없으면 새 UV unwrap + Principled 단색 또는 peel_base_rgb
- 표면 면적 가중 샘플 → UV에 스탬프
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
import numpy as np

from src.blender_sim.fruit_class_mesh_export import (
    BUMP_STRENGTH,
    OBLATE_LEVELS,
    SIZE_LEVELS,
    _apply_bump,
    _apply_shape,
    _clear_scene_objects,
    _decimate_if_needed,
    _import_main_mesh,
    _mesh_cleanup,
    _safe_name,
    _uv_sphere_or_smart,
)


# 베이스 GLB에 알베도 이미지가 없을 때만 사용
_PEEL_RGB = (0.92, 0.52, 0.18)


def _follow_base_color_to_image(socket) -> Optional[bpy.types.Image]:
    """Principled Base Color 소켓에서 Tex Image 노드까지 간단 추적."""
    if socket is None or not socket.is_linked:
        return None
    node = socket.links[0].from_node
    if node.type == "TEX_IMAGE" and getattr(node, "image", None):
        return node.image
    if node.type == "SEPARATE_COLOR":
        return None
    # MixRGB / Hue 등: 입력 쪽 Tex 탐색
    for inp in getattr(node, "inputs", []):
        if getattr(inp, "is_linked", False):
            im = _follow_base_color_to_image(inp)
            if im:
                return im
    return None


def _extract_healthy_albedo_image(obj: bpy.types.Object) -> Optional[bpy.types.Image]:
    """임포트된 베이스 메쉬 재질에서 알베도용 Image 우선 탐색."""
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        tree = mat.node_tree
        for n in tree.nodes:
            if n.type != "BSDF_PRINCIPLED":
                continue
            bc = n.inputs.get("Base Color")
            im = _follow_base_color_to_image(bc)
            if im:
                return im
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        for n in mat.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                return n.image
    return None


def _solid_principled_base_rgb(obj: bpy.types.Object) -> Optional[Tuple[float, float, float]]:
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        for n in mat.node_tree.nodes:
            if n.type != "BSDF_PRINCIPLED":
                continue
            bc = n.inputs.get("Base Color")
            if bc and not bc.is_linked:
                t = bc.default_value
                return (float(t[0]), float(t[1]), float(t[2]))
    return None


def _image_to_atlas_topdown(img: bpy.types.Image, tw: int, th: int) -> np.ndarray:
    """Blender Image → top-down RGBA float, 목표 크기로 리사이즈."""
    w, h = img.size
    flat = np.array(img.pixels[:], dtype=np.float32)
    arr = np.flipud(flat.reshape(h, w, 4))
    return _resize_rgba(arr, tw, th)


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


def _sample_surface_uv(
    obj: bpy.types.Object,
    rng: random.Random,
) -> Tuple[float, float]:
    """면적 가중 삼각형 샘플 → 바리센트릭 일치 UV (0~1)."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    lt = list(mesh.loop_triangles)
    if not lt:
        return 0.5, 0.5

    weights = [max(t.area, 1e-12) for t in lt]
    tri = rng.choices(lt, weights=weights, k=1)[0]
    v = mesh.vertices
    v0 = v[tri.vertices[0]].co.copy()
    v1 = v[tri.vertices[1]].co.copy()
    v2 = v[tri.vertices[2]].co.copy()
    r1 = math.sqrt(rng.random())
    r2 = rng.random()
    bu = 1.0 - r1
    bv = r1 * (1.0 - r2)
    bw = r1 * r2

    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        return 0.5, 0.5
    uvd = uv_layer.data
    l0, l1, l2 = int(tri.loops[0]), int(tri.loops[1]), int(tri.loops[2])
    uv0 = uvd[l0].uv
    uv1 = uvd[l1].uv
    uv2 = uvd[l2].uv
    u = bu * uv0.x + bv * uv1.x + bw * uv2.x
    v = bu * uv0.y + bv * uv1.y + bw * uv2.y
    return float(u % 1.0), float(v % 1.0)


def _load_patch_rgba_topdown(path: Path) -> np.ndarray:
    """Blender로 PNG 로드 후 상단이 행 0인 H×W×4 float32."""
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = "sRGB"
    w, h = img.size
    flat = np.array(img.pixels[:], dtype=np.float32)
    arr = flat.reshape(h, w, 4)
    arr = np.flipud(arr)
    try:
        bpy.data.images.remove(img, do_unlink=True)
    except Exception:
        pass
    return arr


def _resize_rgba(patch: np.ndarray, tw: int, th: int) -> np.ndarray:
    ph, pw = patch.shape[:2]
    if pw == tw and ph == th:
        return patch
    try:
        import cv2

        return cv2.resize(patch, (tw, th), interpolation=cv2.INTER_LINEAR)
    except Exception:
        ys = np.linspace(0, ph - 1, th).astype(int)
        xs = np.linspace(0, pw - 1, tw).astype(int)
        return patch[np.ix_(ys, xs)]


def _rotate_rgba_optional(patch: np.ndarray, deg: float) -> np.ndarray:
    if abs(deg) < 0.5:
        return patch
    try:
        import cv2

        h, w = patch.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
        return cv2.warpAffine(patch, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    except Exception:
        return patch


def _blend_over(dst: np.ndarray, src: np.ndarray, y: int, x: int) -> None:
    """dst에 src 알파 오버 (src가 잘림)."""
    h, w = src.shape[:2]
    H, W = dst.shape[:2]
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(H, y + h), min(W, x + w)
    if y0 >= y1 or x0 >= x1:
        return
    sy0, sx0 = y0 - y, x0 - x
    sy1 = sy0 + (y1 - y0)
    sx1 = sx0 + (x1 - x0)
    s = src[sy0:sy1, sx0:sx1]
    d = dst[y0:y1, x0:x1]
    a = np.clip(s[:, :, 3:4], 0.0, 1.0)
    dst[y0:y1, x0:x1] = a * s + (1.0 - a) * d


def _stamp_uv_texture(
    atlas: np.ndarray,
    patch_top: np.ndarray,
    u: float,
    v: float,
    stamp_uv_radius: float,
    rng: random.Random,
) -> None:
    """패치를 (u,v) 중심으로 UV 텍스처에 스탬프. atlas: H×W×4 top-down."""
    tex_h, tex_w = atlas.shape[:2]
    cx = int(u * (tex_w - 1))
    cy = int((1.0 - v) * (tex_h - 1))
    half = max(int(stamp_uv_radius * min(tex_w, tex_h)), 6)
    ph, pw = patch_top.shape[:2]
    aspect = pw / max(ph, 1)
    target_h = 2 * half
    target_w = max(int(target_h * aspect), 4)
    patch_r = _resize_rgba(patch_top, target_w, target_h)
    patch_r = _rotate_rgba_optional(patch_r, rng.uniform(-25.0, 25.0))
    ph, pw = patch_r.shape[:2]
    x0 = cx - pw // 2
    y0 = cy - ph // 2
    _blend_over(atlas, patch_r, y0, x0)


def _atlas_to_blender_pixels(atlas_top: np.ndarray) -> np.ndarray:
    """상단=행0 → Blender pixels (하단 행 먼저)."""
    return np.flipud(atlas_top).reshape(-1)


def _build_material_uv_albedo(mat_name: str, img_block: bpy.types.Image) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img_block
    tex.interpolation = "Smart"
    uv = nodes.new("ShaderNodeUVMap")
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Alpha" in tex.outputs and "Alpha" in bsdf.inputs:
        links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.52
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _collect_patch_paths_for_class(
    manifest: Dict[str, Any],
    class_name: str,
) -> List[Path]:
    cache_root = Path(manifest["cache_root"])
    prefix = class_name + "/"
    out: List[Path] = []
    for key, meta in manifest.get("images", {}).items():
        nk = key.replace("\\", "/")
        if not nk.startswith(prefix) and not nk.startswith(class_name + "/"):
            continue
        for rel in meta.get("patches") or []:
            p = cache_root / rel.replace("\\", "/")
            if p.is_file():
                out.append(p)
    return out


def run_decal_mesh_export(cfg: Dict[str, Any]) -> None:
    """UV 텍스처 스프레이 모드 (함수명은 진입 호환용)."""
    manifest_path = Path(cfg["manifest_path"]).resolve()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    mesh_paths = [Path(p).resolve() for p in cfg.get("mesh_paths") or []]
    output_root = Path(cfg["output_root"]).resolve()
    fruits_root = Path(cfg["fruits_root"]).resolve()
    total_target = int(cfg.get("total_exports", 15))
    resume = bool(cfg.get("resume", False))
    stamps_n = max(1, int(cfg.get("stamps_per_asset", cfg.get("decals_per_asset", 4))))
    tex_res = max(256, int(cfg.get("texture_resolution", 2048)))
    stamp_uv_radius = float(cfg.get("stamp_uv_radius", 0.06))
    use_healthy_base = bool(cfg.get("use_healthy_albedo_base", True))
    peel_rgb = cfg.get("peel_base_rgb")
    if isinstance(peel_rgb, (list, tuple)) and len(peel_rgb) >= 3:
        peel = (float(peel_rgb[0]), float(peel_rgb[1]), float(peel_rgb[2]))
    else:
        peel = _PEEL_RGB

    if not mesh_paths:
        print("[uv_texture_export] mesh_paths empty")
        return

    class_dirs = sorted(
        [p for p in fruits_root.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    )
    if not class_dirs:
        print(f"[uv_texture_export] No class folders under {fruits_root}")
        return

    n_cls = len(class_dirs)
    base = total_target // n_cls
    extra = total_target % n_cls
    counts = [base + (1 if i < extra else 0) for i in range(n_cls)]
    print(
        f"[uv_texture_export] {n_cls} classes, counts={counts} (total {sum(counts)}) → {output_root}"
    )

    variant_idx = 0
    done = skipped = failed = 0

    for ci, class_dir in enumerate(class_dirs):
        class_name = class_dir.name
        patch_paths = _collect_patch_paths_for_class(manifest, class_name)
        out_sub = output_root / _safe_name(class_name)
        out_sub.mkdir(parents=True, exist_ok=True)
        per_class = counts[ci]

        if not patch_paths:
            print(f"[uv_texture_export] WARN: no patches for class '{class_name}' — skip")
            for _ in range(per_class):
                variant_idx += 1
            continue

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
                hashlib.md5(f"{class_name}-{local_i}-{variant_idx}-uvtex".encode()).digest()[:4],
                "little",
            )
            rng = random.Random(seed)
            stem = _safe_name(mesh_path.stem)
            out_file = out_sub / f"{stem}__v{local_i:02d}_s{si}_o{oi}_b{bi}_tpaint.glb"

            if resume and out_file.is_file() and out_file.stat().st_size > 0:
                skipped += 1
                variant_idx += 1
                continue

            print(f"[uv_texture_export] {class_name} / {out_file.name}", flush=True)

            try:
                _clear_scene_objects()
                fruit = _import_main_mesh(mesh_path)
                healthy_img = _extract_healthy_albedo_image(fruit) if use_healthy_base else None

                _apply_shape(fruit, size, obl)
                _apply_bump(fruit, bump, seed)
                _decimate_if_needed(fruit, max_faces=10000)
                _mesh_cleanup(fruit)

                # 건강 베이스 GLB의 알베도가 있으면 그걸 텍스처 베이스로 쓰고, 기존 UV 유지
                if healthy_img is not None:
                    atlas = _image_to_atlas_topdown(healthy_img, tex_res, tex_res)
                    if atlas.shape[2] == 3:
                        a = np.ones((*atlas.shape[:2], 1), dtype=np.float32)
                        atlas = np.concatenate([atlas, a], axis=2)
                    print(
                        f"[uv_texture_export] healthy 베이스 알베도 사용: {healthy_img.name} ({healthy_img.size[0]}×{healthy_img.size[1]})",
                        flush=True,
                    )
                else:
                    _uv_sphere_or_smart(fruit)
                    solid = _solid_principled_base_rgb(fruit)
                    fill = solid if solid is not None else peel
                    atlas = np.zeros((tex_res, tex_res, 4), dtype=np.float32)
                    atlas[:, :, 0] = fill[0]
                    atlas[:, :, 1] = fill[1]
                    atlas[:, :, 2] = fill[2]
                    atlas[:, :, 3] = 1.0

                for _ in range(stamps_n):
                    pp = rng.choice(patch_paths)
                    patch = _load_patch_rgba_topdown(pp)
                    u, v = _sample_surface_uv(fruit, rng)
                    _stamp_uv_texture(atlas, patch, u, v, stamp_uv_radius, rng)

                albedo = bpy.data.images.new(
                    f"Albedo_{stem}_{local_i}",
                    width=tex_res,
                    height=tex_res,
                    alpha=True,
                )
                albedo.colorspace_settings.name = "sRGB"
                flat = _atlas_to_blender_pixels(atlas).astype(np.float32)
                if hasattr(albedo.pixels, "foreach_set"):
                    albedo.pixels.foreach_set(flat)
                else:
                    albedo.pixels = flat.tolist()

                mat = _build_material_uv_albedo(f"Mat_{stem}_{local_i}", albedo)
                fruit.data.materials.clear()
                fruit.data.materials.append(mat)

                _export_glb(out_file)

                try:
                    bpy.data.images.remove(albedo, do_unlink=True)
                except Exception:
                    pass
                done += 1
            except Exception as e:
                print(f"[uv_texture_export] Fail {out_file.name}: {e}")
                failed += 1

            variant_idx += 1

    print(f"[uv_texture_export] Done. {done} written, {skipped} skipped, {failed} failed")
