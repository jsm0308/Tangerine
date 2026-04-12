# src/blender_sim/disease_materials.py
"""
병해 절차 재질 — glTF/GLB 호환을 위해 Surface 는 항상 **Principled BSDF 1개**만 연결합니다.
(Mix Shader 로 BSDF 를 섞으면 내보낸 GLB 가 뷰어에서 깨지는 경우가 많습니다.)

Dispatcher: apply_disease_material(obj, disease: str, disease_params: dict)
"""

from __future__ import annotations

import bpy


def _new_mat(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat


def _n(nodes, node_type: str, loc=(0, 0)):
    node = nodes.new(type=node_type)
    node.location = loc
    return node


def _l(tree, src, src_sock, dst, dst_sock):
    tree.links.new(src.outputs[src_sock], dst.inputs[dst_sock])


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


def _rgb_const(nodes, tree, color_rgba, loc):
    """ShaderNodeRGB — (r,g,b,a) 튜플."""
    n = _n(nodes, "ShaderNodeRGB", loc)
    n.outputs[0].default_value = tuple(color_rgba[:4]) if len(color_rgba) >= 4 else tuple(color_rgba[:3]) + (1.0,)
    return n


def _mix_rgb(nodes, tree, loc, fac_sock, a_sock, b_sock):
    """Fac·Color1·Color2 소켓 → 혼합 RGB. MixRGB 우선, 실패 시 ShaderNodeMix."""
    try:
        m = nodes.new("ShaderNodeMixRGB")
        m.location = loc
        tree.links.new(fac_sock, m.inputs["Fac"])
        tree.links.new(a_sock, m.inputs["Color1"])
        tree.links.new(b_sock, m.inputs["Color2"])
        return m.outputs["Color"]
    except Exception:
        m = nodes.new("ShaderNodeMix")
        m.location = loc
        m.data_type = "RGBA"
        m.blend_type = "MIX"
        tree.links.new(fac_sock, m.inputs["Factor"])
        tree.links.new(a_sock, m.inputs["A"])
        tree.links.new(b_sock, m.inputs["B"])
        return m.outputs["Result"]


# ─── 1. Healthy ──────────────────────────────────────────────────────────────


def apply_healthy(obj, params: dict):
    mat = _new_mat(f"healthy__{obj.name}")
    nd, lk = mat.node_tree.nodes, mat.node_tree

    out = _n(nd, "ShaderNodeOutputMaterial", (400, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (0, 0))

    bsdf.inputs["Base Color"].default_value = tuple(params["base_color"])
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    _specular(bsdf, params.get("specular", 0.5))

    _l(lk, bsdf, "BSDF", out, "Surface")
    _assign(obj, mat)
    return mat


# ─── 2. Black Spot ───────────────────────────────────────────────────────────


def apply_black_spot(obj, params: dict):
    mat = _new_mat(f"black_spot__{obj.name}")
    nd, lk = mat.node_tree.nodes, mat.node_tree

    out = _n(nd, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (700, 0))
    ramp = _n(nd, "ShaderNodeValToRGB", (200, 0))
    vor = _n(nd, "ShaderNodeTexVoronoi", (-100, 80))
    bump = _n(nd, "ShaderNodeBump", (500, -280))
    noise = _n(nd, "ShaderNodeTexNoise", (200, -280))
    tc = _n(nd, "ShaderNodeTexCoord", (-380, 0))
    bw = _n(nd, "ShaderNodeRGBToBW", (400, 0))

    ca = _rgb_const(nd, lk, params["base_color"], (420, 120))
    cb = _rgb_const(nd, lk, params["spot_color"], (420, -80))

    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = params["spot_scale"]

    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (1, 1, 1, 1)
    cr.elements[1].position = params["spot_threshold"]
    cr.elements[1].color = (0, 0, 0, 1)

    bump.inputs["Strength"].default_value = params["bump_strength"]
    bump.inputs["Distance"].default_value = 0.005
    noise.inputs["Scale"].default_value = params["bump_noise_scale"]
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.7

    _l(lk, tc, "Object", vor, "Vector")
    _l(lk, tc, "Object", noise, "Vector")
    _l(lk, vor, "Distance", ramp, "Fac")
    _l(lk, ramp, "Color", bw, "Color")

    col = _mix_rgb(nd, lk, (520, 0), bw.outputs["Val"], ca.outputs["Color"], cb.outputs["Color"])
    lk.links.new(col, bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.32
    _l(lk, noise, "Fac", bump, "Height")
    _l(lk, bump, "Normal", bsdf, "Normal")

    _l(lk, bsdf, "BSDF", out, "Surface")
    _assign(obj, mat)
    return mat


# ─── 3. Canker ────────────────────────────────────────────────────────────────


def apply_canker(obj, params: dict):
    mat = _new_mat(f"canker__{obj.name}")
    nd, lk = mat.node_tree.nodes, mat.node_tree

    out = _n(nd, "ShaderNodeOutputMaterial", (1100, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (900, 0))
    ramp_h = _n(nd, "ShaderNodeValToRGB", (200, 80))
    ramp_l = _n(nd, "ShaderNodeValToRGB", (200, -80))
    vor = _n(nd, "ShaderNodeTexVoronoi", (-100, 0))
    bump = _n(nd, "ShaderNodeBump", (700, -320))
    noise = _n(nd, "ShaderNodeTexNoise", (400, -320))
    tc = _n(nd, "ShaderNodeTexCoord", (-380, 0))
    bwh = _n(nd, "ShaderNodeRGBToBW", (400, 80))
    bwl = _n(nd, "ShaderNodeRGBToBW", (400, -80))

    c_base = _rgb_const(nd, lk, params["base_color"], (520, 200))
    c_halo = _rgb_const(nd, lk, params["halo_color"], (520, 40))
    c_les = _rgb_const(nd, lk, params["lesion_color"], (520, -120))

    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = params["lesion_scale"]

    ch = ramp_h.color_ramp
    ch.interpolation = "EASE"
    ch.elements[0].position = 0.0
    ch.elements[0].color = (1, 1, 1, 1)
    ch.elements[1].position = 0.22
    ch.elements[1].color = (0, 0, 0, 1)

    cl = ramp_l.color_ramp
    cl.interpolation = "EASE"
    cl.elements[0].position = 0.0
    cl.elements[0].color = (1, 1, 1, 1)
    cl.elements[1].position = 0.09
    cl.elements[1].color = (0, 0, 0, 1)

    bump.inputs["Strength"].default_value = params["bump_strength"]
    bump.inputs["Distance"].default_value = params["bump_distance"]
    noise.inputs["Scale"].default_value = 25.0
    noise.inputs["Detail"].default_value = 6.0

    _l(lk, tc, "Object", vor, "Vector")
    _l(lk, tc, "Object", noise, "Vector")
    _l(lk, vor, "Distance", ramp_h, "Fac")
    _l(lk, vor, "Distance", ramp_l, "Fac")
    _l(lk, ramp_h, "Color", bwh, "Color")
    _l(lk, ramp_l, "Color", bwl, "Color")

    # inner = lerp(lesion, halo, fac_l)
    inner = _mix_rgb(nd, lk, (620, -40), bwl.outputs["Val"], c_les.outputs["Color"], c_halo.outputs["Color"])
    # final = lerp(base, inner, fac_h)
    final = _mix_rgb(nd, lk, (740, 40), bwh.outputs["Val"], c_base.outputs["Color"], inner)
    lk.links.new(final, bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.38
    _l(lk, noise, "Fac", bump, "Height")
    _l(lk, bump, "Normal", bsdf, "Normal")

    _l(lk, bsdf, "BSDF", out, "Surface")
    _assign(obj, mat)
    return mat


# ─── 4. Greening ───────────────────────────────────────────────────────────────


def apply_greening(obj, params: dict):
    mat = _new_mat(f"greening__{obj.name}")
    nd, lk = mat.node_tree.nodes, mat.node_tree

    out = _n(nd, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (700, 0))
    ramp_n = _n(nd, "ShaderNodeValToRGB", (0, 80))
    ramp_z = _n(nd, "ShaderNodeValToRGB", (0, -80))
    bw_n = _n(nd, "ShaderNodeRGBToBW", (180, 80))
    bw_z = _n(nd, "ShaderNodeRGBToBW", (180, -80))
    math_mul = _n(nd, "ShaderNodeMath", (320, 0))
    noise = _n(nd, "ShaderNodeTexNoise", (-300, 80))
    sep = _n(nd, "ShaderNodeSeparateXYZ", (-300, -80))
    tc = _n(nd, "ShaderNodeTexCoord", (-550, 0))

    c_o = _rgb_const(nd, lk, params["orange_color"], (520, 80))
    c_g = _rgb_const(nd, lk, params["green_color"], (520, -80))

    noise.inputs["Scale"].default_value = params["mottle_scale"]
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.6

    cn = ramp_n.color_ramp
    cn.elements[0].position = 0.35
    cn.elements[0].color = (0, 0, 0, 1)
    cn.elements[1].position = 0.65
    cn.elements[1].color = (1, 1, 1, 1)

    ratio = params.get("green_bottom_ratio", 0.45)
    cz = ramp_z.color_ramp
    cz.elements[0].position = 0.0
    cz.elements[0].color = (0, 0, 0, 1)
    cz.elements[1].position = ratio
    cz.elements[1].color = (1, 1, 1, 1)

    math_mul.operation = "MULTIPLY"

    _l(lk, tc, "Object", noise, "Vector")
    _l(lk, tc, "Object", sep, "Vector")
    _l(lk, noise, "Fac", ramp_n, "Fac")
    _l(lk, sep, "Z", ramp_z, "Fac")
    _l(lk, ramp_n, "Color", bw_n, "Color")
    _l(lk, ramp_z, "Color", bw_z, "Color")
    _l(lk, bw_n, "Val", math_mul, 0)
    _l(lk, bw_z, "Val", math_mul, 1)

    # lerp(green, orange, fac) — Mix Fac 0 → Color1, Fac 1 → Color2 로 맞춤
    mout = math_mul.outputs.get("Value") or math_mul.outputs[0]
    col = _mix_rgb(nd, lk, (520, 0), mout, c_g.outputs["Color"], c_o.outputs["Color"])
    lk.links.new(col, bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.33
    _l(lk, bsdf, "BSDF", out, "Surface")
    _assign(obj, mat)
    return mat


# ─── 5. Scab ───────────────────────────────────────────────────────────────────


def apply_scab(obj, params: dict):
    mat = _new_mat(f"scab__{obj.name}")
    nd, lk = mat.node_tree.nodes, mat.node_tree

    out = _n(nd, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (700, 0))
    ramp = _n(nd, "ShaderNodeValToRGB", (200, 0))
    vor = _n(nd, "ShaderNodeTexVoronoi", (-100, 80))
    bump = _n(nd, "ShaderNodeBump", (500, -280))
    noise = _n(nd, "ShaderNodeTexNoise", (200, -280))
    tc = _n(nd, "ShaderNodeTexCoord", (-380, 0))
    bw = _n(nd, "ShaderNodeRGBToBW", (400, 0))

    c_o = _rgb_const(nd, lk, params["base_color"], (420, 120))
    c_sc = _rgb_const(nd, lk, params["scab_color"], (420, -80))

    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = params["scab_scale"]

    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (1, 1, 1, 1)
    cr.elements[1].position = 0.30
    cr.elements[1].color = (0, 0, 0, 1)

    bump.inputs["Strength"].default_value = params["bump_strength"]
    bump.inputs["Distance"].default_value = params["bump_distance"]
    noise.inputs["Scale"].default_value = 40.0
    noise.inputs["Detail"].default_value = 10.0

    _l(lk, tc, "Object", vor, "Vector")
    _l(lk, tc, "Object", noise, "Vector")
    _l(lk, vor, "Distance", ramp, "Fac")
    _l(lk, ramp, "Color", bw, "Color")

    col = _mix_rgb(nd, lk, (520, 0), bw.outputs["Val"], c_o.outputs["Color"], c_sc.outputs["Color"])
    lk.links.new(col, bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = float(params.get("wart_roughness", 0.9))

    _l(lk, noise, "Fac", bump, "Height")
    _l(lk, bump, "Normal", bsdf, "Normal")

    _l(lk, bsdf, "BSDF", out, "Surface")
    _assign(obj, mat)
    return mat


# ─── dispatcher ──────────────────────────────────────────────────────────────

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
