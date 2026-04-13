# src/blender_sim/disease_materials.py
"""
병해 재질 — glTF/GLB 호환을 위해 **알베도는 PNG(Image Texture + UV)** 로만 입힙니다.
(절차적 노이즈/보로노이는 scripts/gen_disease_texture_masks.py 가 미리 베이크.)

Dispatcher: apply_disease_material(obj, disease: str, disease_params: dict)
"""

from __future__ import annotations

from pathlib import Path

import bpy

_HERE = Path(__file__).resolve().parent


def _project_root() -> Path:
    return _HERE.parents[1]


def _texture_path(filename: str) -> Path:
    p = _project_root() / "assets" / "textures" / "disease" / filename
    if not p.is_file():
        raise FileNotFoundError(
            f"병해 텍스처 없음: {p} — python scripts/gen_disease_texture_masks.py 실행"
        )
    return p


def _new_mat(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat


def _n(nodes, node_type: str, loc=(0, 0)):
    node = nodes.new(type=node_type)
    node.location = loc
    return node


def _assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def _specular(bsdf, value: float) -> None:
    for key in ("Specular", "Specular IOR Level"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = value
            return


def _load_image(abs_path: Path):
    abs_path = abs_path.resolve()
    for img in bpy.data.images:
        try:
            if Path(bpy.path.abspath(img.filepath)) == abs_path:
                return img
        except Exception:
            continue
    img = bpy.data.images.load(str(abs_path), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    return img


def _apply_textured(
    obj,
    mat_name: str,
    png_name: str,
    *,
    roughness: float,
    specular: float = 0.5,
):
    mat = _new_mat(mat_name)
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links

    out = _n(nd, "ShaderNodeOutputMaterial", (320, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (40, 0))
    tex = _n(nd, "ShaderNodeTexImage", (-260, 0))
    tc = _n(nd, "ShaderNodeTexCoord", (-560, 0))

    tex.image = _load_image(_texture_path(png_name))
    lk.new(tc.outputs["UV"], tex.inputs["Vector"])
    lk.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    _specular(bsdf, specular)
    lk.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _assign(obj, mat)
    return mat


# ─── 1. Healthy ──────────────────────────────────────────────────────────────


def apply_healthy(obj, params: dict):
    mat = _new_mat(f"healthy__{obj.name}")
    nd = mat.node_tree.nodes
    links = mat.node_tree.links

    out = _n(nd, "ShaderNodeOutputMaterial", (400, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (0, 0))

    bsdf.inputs["Base Color"].default_value = tuple(params["base_color"])
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    _specular(bsdf, params.get("specular", 0.5))

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _assign(obj, mat)
    return mat


# ─── 2–5. PNG 알베도 (variants_batch roughness 키가 있으면 사용) ───────────────


def apply_black_spot(obj, params: dict):
    return _apply_textured(
        obj,
        f"black_spot__{obj.name}",
        "black_spot_albedo.png",
        roughness=float(params.get("roughness", 0.32)),
        specular=float(params.get("specular", 0.45)),
    )


def apply_canker(obj, params: dict):
    return _apply_textured(
        obj,
        f"canker__{obj.name}",
        "canker_albedo.png",
        roughness=float(params.get("roughness", 0.38)),
        specular=float(params.get("specular", 0.42)),
    )


def apply_greening(obj, params: dict):
    return _apply_textured(
        obj,
        f"greening__{obj.name}",
        "greening_albedo.png",
        roughness=float(params.get("roughness", 0.33)),
        specular=float(params.get("specular", 0.48)),
    )


def apply_scab(obj, params: dict):
    return _apply_textured(
        obj,
        f"scab__{obj.name}",
        "scab_albedo.png",
        roughness=float(params.get("wart_roughness", 0.92)),
        specular=float(params.get("specular", 0.35)),
    )


DISEASE_FUNCS = {
    "healthy": apply_healthy,
    "black_spot": apply_black_spot,
    "canker": apply_canker,
    "greening": apply_greening,
    "scab": apply_scab,
}


def apply_disease_material(obj, disease: str, disease_params: dict):
    fn = DISEASE_FUNCS.get(disease)
    if fn is None:
        raise ValueError(f"Unknown disease '{disease}'. Valid: {list(DISEASE_FUNCS)}")
    return fn(obj, disease_params[disease])
