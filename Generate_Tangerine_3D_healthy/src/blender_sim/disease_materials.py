# src/blender_sim/disease_materials.py
"""
병해 재질 — 프롬프트 스펙 기반 절차적 노드(Blender Cycles).

glTF/Windows 3D Viewer 호환: `generate_variants.py`가 내보내기 전
`gltf_material_bake.simplify_materials_for_gltf_export`로 알베도 EMIT·거칠기(그레이)·
접선 노멀(지오메트리)을 베이크해 단순 PBR 재질로 바꾼다.
(미베이크 시 절차 노드가 끊겨 알베도가 흰색으로 보일 수 있음.)

Dispatcher: apply_disease_material(obj, disease: str, disease_params: dict)
"""

from __future__ import annotations

import bpy


def _new_mat(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    if hasattr(mat, "displacement_method"):
        mat.displacement_method = "BOTH"
    return mat


def _n(nodes, node_type: str, loc=(0.0, 0.0)):
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


def _hex_rgba(hex_str: str, a: float = 1.0) -> tuple:
    h = hex_str.strip().lstrip("#")
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
        a,
    )


def _mix_rgba(nodes, links, fac, sock_a, sock_b, loc):
    try:
        m = nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = "MIX"
        m.location = loc
        links.new(fac, m.inputs["Factor"])
        links.new(sock_a, m.inputs["A"])
        links.new(sock_b, m.inputs["B"])
        return m.outputs["Result"]
    except Exception:
        m = nodes.new("ShaderNodeMixRGB")
        m.location = loc
        links.new(fac, m.inputs["Fac"])
        links.new(sock_a, m.inputs["Color1"])
        links.new(sock_b, m.inputs["Color2"])
        return m.outputs["Color"]


def _mix_float(nodes, links, fac, a_sock, b_sock, loc):
    m = nodes.new("ShaderNodeMix")
    m.data_type = "FLOAT"
    m.location = loc
    links.new(fac, m.inputs["Factor"])
    links.new(a_sock, m.inputs["A"])
    links.new(b_sock, m.inputs["B"])
    return m.outputs["Result"]


def _rgb_const(nodes, rgba, loc):
    n = _n(nodes, "ShaderNodeRGB", loc)
    n.outputs[0].default_value = rgba
    return n.outputs["Color"]


def _zero_displacement(nodes, links, out_mat):
    c = _n(nodes, "ShaderNodeCombineXYZ", (out_mat.location[0] + 40, out_mat.location[1] - 200))
    c.inputs["X"].default_value = 0.0
    c.inputs["Y"].default_value = 0.0
    c.inputs["Z"].default_value = 0.0
    links.new(c.outputs["Vector"], out_mat.inputs["Displacement"])


def _noise_scalar_out(noise):
    if "Fac" in noise.outputs:
        return noise.outputs["Fac"]
    return noise.outputs["Color"]


def _vor_metric_euclidean(vor):
    try:
        vor.distance = "EUCLIDEAN"
    except Exception:
        pass


# ─── Healthy ─────────────────────────────────────────────────────────────────


def apply_healthy(obj, params: dict):
    mat = _new_mat(f"healthy__{obj.name}")
    nd, links = mat.node_tree.nodes, mat.node_tree.links
    out = _n(nd, "ShaderNodeOutputMaterial", (400, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (0, 0))
    bsdf.inputs["Base Color"].default_value = tuple(params["base_color"])
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    _specular(bsdf, params.get("specular", 0.5))
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _zero_displacement(nd, links, out)
    _assign(obj, mat)
    return mat


# ─── 1. Black Spot ───────────────────────────────────────────────────────────


def apply_black_spot(obj, params: dict):
    mat = _new_mat(f"black_spot__{obj.name}")
    nd, links = mat.node_tree.nodes, mat.node_tree.links

    out = _n(nd, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (620, 0))
    tc = _n(nd, "ShaderNodeTexCoord", (-800, 0))
    vor = _n(nd, "ShaderNodeTexVoronoi", (-560, 0))
    ramp = _n(nd, "ShaderNodeValToRGB", (-320, 0))
    bump_n = _n(nd, "ShaderNodeBump", (420, -220))
    noise = _n(nd, "ShaderNodeTexNoise", (-200, -280))

    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    _vor_metric_euclidean(vor)
    vor.inputs["Scale"].default_value = float(params.get("voronoi_scale", 175.0))
    if "Randomness" in vor.inputs:
        vor.inputs["Randomness"].default_value = 1.0

    links.new(tc.outputs["Object"], vor.inputs["Vector"])
    dist_sock = vor.outputs.get("Distance") or vor.outputs[1]
    # 거리는 0~1이 아님 → Fac에 넣기 전 정규화하지 않으면 램프가 한쪽만 선택되어 색이 뒤집혀 보임
    dmap = _n(nd, "ShaderNodeMapRange", (-380, 0))
    dmap.inputs["From Min"].default_value = 0.0
    dmap.inputs["From Max"].default_value = float(params.get("spot_dist_map_max", 0.18))
    dmap.inputs["To Min"].default_value = 0.0
    dmap.inputs["To Max"].default_value = 1.0
    if hasattr(dmap, "use_clamp"):
        dmap.use_clamp = True
    links.new(dist_sock, dmap.inputs["Value"])
    links.new(dmap.outputs["Result"], ramp.inputs["Fac"])

    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (1, 1, 1, 1)
    # 정규화된 Fac에서 좁은 구간만 반점(흰 마스크→어두운 색)
    cr.elements[1].position = float(params.get("spot_ramp_pos", 0.17))
    cr.elements[1].color = (0, 0, 0, 1)

    bw = _n(nd, "ShaderNodeRGBToBW", (-120, 40))
    links.new(ramp.outputs["Color"], bw.inputs["Color"])
    spot_mask = bw.outputs["Val"]

    c_orange = _rgb_const(nd, _hex_rgba("#FFA500"), (180, 140))
    c_dark = _rgb_const(nd, _hex_rgba("#1A0F0A"), (180, -40))
    # Fac=spot_dark: 1=반점(어둡), 0=건강(주황). inv 후 bw는 반점=1에 가깝게
    col = _mix_rgba(nd, links, spot_mask, c_orange, c_dark, (380, 60))
    links.new(col, bsdf.inputs["Base Color"])

    r_orange = _n(nd, "ShaderNodeValue", (380, -80))
    r_orange.outputs[0].default_value = 0.35
    r_spot = _n(nd, "ShaderNodeValue", (380, -140))
    r_spot.outputs[0].default_value = 0.85
    rough = _mix_float(nd, links, spot_mask, r_orange.outputs[0], r_spot.outputs[0], (500, -100))
    links.new(rough, bsdf.inputs["Roughness"])

    noise.inputs["Scale"].default_value = 250.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.65
    links.new(tc.outputs["Object"], noise.inputs["Vector"])

    nsc = _noise_scalar_out(noise)
    mul_b = _n(nd, "ShaderNodeMath", (200, -200))
    mul_b.operation = "MULTIPLY"
    links.new(spot_mask, mul_b.inputs[0])
    links.new(nsc, mul_b.inputs[1])

    bump_n.inputs["Strength"].default_value = 0.8
    bump_n.inputs["Distance"].default_value = 0.001
    links.new(mul_b.outputs[0], bump_n.inputs["Height"])
    links.new(bump_n.outputs["Normal"], bsdf.inputs["Normal"])

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _zero_displacement(nd, links, out)
    _assign(obj, mat)
    return mat


# ─── 2. Canker — 3-stop color + matching roughness / disp ramps on same DE ───


def apply_canker(obj, params: dict):
    mat = _new_mat(f"canker__{obj.name}")
    nd, links = mat.node_tree.nodes, mat.node_tree.links

    out = _n(nd, "ShaderNodeOutputMaterial", (1000, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (780, 0))
    tc = _n(nd, "ShaderNodeTexCoord", (-900, 0))
    vor = _n(nd, "ShaderNodeTexVoronoi", (-660, 0))
    r_col = _n(nd, "ShaderNodeValToRGB", (-400, 120))
    r_rough = _n(nd, "ShaderNodeValToRGB", (-400, -40))
    r_hgt = _n(nd, "ShaderNodeValToRGB", (-400, -220))
    disp = _n(nd, "ShaderNodeDisplacement", (620, -300))

    vor.voronoi_dimensions = "3D"
    vor.feature = "DISTANCE_TO_EDGE"
    _vor_metric_euclidean(vor)
    vor.inputs["Scale"].default_value = float(params.get("lesion_scale", 25.0))
    if "Randomness" in vor.inputs:
        vor.inputs["Randomness"].default_value = 0.45

    links.new(tc.outputs["Object"], vor.inputs["Vector"])
    de = vor.outputs.get("Distance") or vor.outputs[1]
    # Distance-to-edge 범위를 0~1로 맞춰 궤양이 표면의 ~5–10%에 몰리도록 튜닝
    dem = _n(nd, "ShaderNodeMapRange", (-520, 0))
    dem.inputs["From Min"].default_value = 0.0
    dem.inputs["From Max"].default_value = float(params.get("canker_de_span", 0.30))
    dem.inputs["To Min"].default_value = 0.0
    dem.inputs["To Max"].default_value = 1.0
    if hasattr(dem, "use_clamp"):
        dem.use_clamp = True
    links.new(de, dem.inputs["Value"])
    de_n = dem.outputs["Result"]
    links.new(de_n, r_col.inputs["Fac"])
    links.new(de_n, r_rough.inputs["Fac"])
    links.new(de_n, r_hgt.inputs["Fac"])

    # 알베도: 코르크 중심 → 할로 → 베이스 오렌지
    c0 = r_col.color_ramp
    c0.interpolation = "EASE"
    c0.elements[0].position = 0.0
    c0.elements[0].color = _hex_rgba("#6B4E31")
    c0.elements[1].position = 0.1
    c0.elements[1].color = _hex_rgba("#F9E076")
    elc = c0.elements.new(0.22)
    elc.color = _hex_rgba("#FF9E1B")

    links.new(r_col.outputs["Color"], bsdf.inputs["Base Color"])

    # 거칠기: 동일 구간에 맞춘 그레이스케일
    g0 = r_rough.color_ramp
    g0.interpolation = "EASE"
    g0.elements[0].position = 0.0
    g0.elements[0].color = (0.95, 0.95, 0.95, 1)
    g0.elements[1].position = 0.1
    g0.elements[1].color = (0.15, 0.15, 0.15, 1)
    elg = g0.elements.new(0.22)
    elg.color = (0.3, 0.3, 0.3, 1)

    bw_r = _n(nd, "ShaderNodeRGBToBW", (520, -20))
    links.new(r_rough.outputs["Color"], bw_r.inputs["Color"])
    links.new(bw_r.outputs["Val"], bsdf.inputs["Roughness"])

    # 변위 높이: 코르크 음, 할로 양, 바깥 0 근사 (0~1 → 맵)
    h0 = r_hgt.color_ramp
    h0.interpolation = "CONSTANT"
    h0.elements[0].position = 0.0
    h0.elements[0].color = (0.0, 0.0, 0.0, 1)
    h0.elements[1].position = 0.08
    h0.elements[1].color = (0.5, 0.0, 0.0, 1)
    elh = h0.elements.new(0.18)
    elh.color = (1.0, 0.0, 0.0, 1)

    mr = _n(nd, "ShaderNodeMapRange", (420, -240))
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = -0.002
    mr.inputs["To Max"].default_value = 0.003
    bw_h = _n(nd, "ShaderNodeRGBToBW", (240, -220))
    links.new(r_hgt.outputs["Color"], bw_h.inputs["Color"])
    links.new(bw_h.outputs["Val"], mr.inputs["Value"])
    links.new(mr.outputs["Result"], disp.inputs["Height"])
    disp.inputs["Scale"].default_value = 1.0
    disp.inputs["Midlevel"].default_value = 0.0
    links.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _assign(obj, mat)
    return mat


# ─── 3. Greening (HLB) ───────────────────────────────────────────────────────


def apply_greening(obj, params: dict):
    mat = _new_mat(f"greening__{obj.name}")
    nd, links = mat.node_tree.nodes, mat.node_tree.links

    out = _n(nd, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (680, 0))
    tc = _n(nd, "ShaderNodeTexCoord", (-820, 0))
    # Blender 5: 구 Musgrave → Noise(Multifractal) 로 근사 (Detail·Scale 스펙)
    mus = _n(nd, "ShaderNodeTexNoise", (-580, 120))
    nz = _n(nd, "ShaderNodeTexNoise", (-580, -80))
    ramp_m = _n(nd, "ShaderNodeValToRGB", (-340, 40))
    sep = _n(nd, "ShaderNodeSeparateXYZ", (-580, -280))
    grad = _n(nd, "ShaderNodeMapRange", (-360, -260))

    try:
        mus.noise_type = "MULTIFRACTAL"
    except Exception:
        pass
    mus.inputs["Scale"].default_value = float(params.get("mottle_scale", 3.0))
    mus.inputs["Detail"].default_value = 10.0
    mus.inputs["Roughness"].default_value = 0.5
    try:
        nz.noise_type = "FBM"
    except Exception:
        pass
    nz.inputs["Scale"].default_value = float(params.get("greening_noise_scale", 8.0))
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.55

    links.new(tc.outputs["Object"], mus.inputs["Vector"])
    links.new(tc.outputs["Object"], nz.inputs["Vector"])
    links.new(tc.outputs["Object"], sep.inputs["Vector"])

    mix_n = _n(nd, "ShaderNodeMixRGB", (-420, 20))
    mix_n.blend_type = "MIX"
    mix_n.inputs["Fac"].default_value = 0.5
    links.new(mus.outputs["Color"], mix_n.inputs["Color1"])
    links.new(nz.outputs["Color"], mix_n.inputs["Color2"])

    links.new(mix_n.outputs["Color"], ramp_m.inputs["Fac"])
    rm = ramp_m.color_ramp
    rm.interpolation = "EASE"
    # 얼룩이 표면의 대략 50~70%를 덮도록
    rm.elements[0].position = float(params.get("mottle_ramp_lo", 0.2))
    rm.elements[0].color = (0, 0, 0, 1)
    rm.elements[1].position = float(params.get("mottle_ramp_hi", 0.78))
    rm.elements[1].color = (1, 1, 1, 1)

    # Object 공간 Z: 아래쪽(Z<0)일수록 올리브 쪽으로 몰아줌 (황룡 색역전 느낌)
    grad.inputs["From Min"].default_value = -1.0
    grad.inputs["From Max"].default_value = 0.35
    grad.inputs["To Min"].default_value = 1.0
    grad.inputs["To Max"].default_value = 0.0
    if hasattr(grad, "use_clamp"):
        grad.use_clamp = True
    links.new(sep.outputs["Z"], grad.inputs["Value"])

    mottle = _n(nd, "ShaderNodeRGBToBW", (-200, 40))
    links.new(ramp_m.outputs["Color"], mottle.inputs["Color"])

    comb = _n(nd, "ShaderNodeMath", (-40, -80))
    comb.operation = "MULTIPLY"
    links.new(mottle.outputs["Val"], comb.inputs[0])
    links.new(grad.outputs["Result"], comb.inputs[1])

    c_yellow = _rgb_const(nd, _hex_rgba("#E5C158"), (120, 180))
    c_olive = _rgb_const(nd, _hex_rgba("#7B904B"), (120, 20))
    c_orange = _rgb_const(nd, _hex_rgba("#FF9E1B"), (120, -140))

    mx1 = _mix_rgba(nd, links, mottle.outputs["Val"], c_orange, c_yellow, (300, 100))
    # fac 높을수록 올리브(하부·얼룩 강조)
    mx2 = _mix_rgba(nd, links, comb.outputs[0], mx1, c_olive, (480, 40))
    links.new(mx2, bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = float(params.get("roughness", 0.5))
    _specular(bsdf, 0.45)

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _zero_displacement(nd, links, out)
    _assign(obj, mat)
    return mat


# ─── 4. Scab ─────────────────────────────────────────────────────────────────


def apply_scab(obj, params: dict):
    mat = _new_mat(f"scab__{obj.name}")
    nd, links = mat.node_tree.nodes, mat.node_tree.links

    out = _n(nd, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nd, "ShaderNodeBsdfPrincipled", (620, 0))
    tc = _n(nd, "ShaderNodeTexCoord", (-800, 0))
    n1 = _n(nd, "ShaderNodeTexNoise", (-560, 80))
    n2 = _n(nd, "ShaderNodeTexNoise", (-560, -100))
    ramp = _n(nd, "ShaderNodeValToRGB", (-300, 0))
    disp = _n(nd, "ShaderNodeDisplacement", (500, -280))

    try:
        n1.noise_type = "FBM"
    except Exception:
        pass
    n1.inputs["Scale"].default_value = float(params.get("scab_noise_a_scale", 22.0))
    n1.inputs["Detail"].default_value = 12.0
    n1.inputs["Roughness"].default_value = 0.7
    try:
        n2.noise_type = "RIDGED_MULTIFRACTAL"
    except Exception:
        pass
    n2.inputs["Scale"].default_value = float(params.get("scab_noise_b_scale", 15.0))
    n2.inputs["Detail"].default_value = 12.0
    n2.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], n1.inputs["Vector"])
    links.new(tc.outputs["Object"], n2.inputs["Vector"])

    mix_w = _n(nd, "ShaderNodeMixRGB", (-420, -20))
    mix_w.inputs["Fac"].default_value = 0.55
    links.new(n1.outputs["Color"], mix_w.inputs["Color1"])
    links.new(n2.outputs["Color"], mix_w.inputs["Color2"])

    links.new(mix_w.outputs["Color"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (1, 1, 1, 1)
    cr.elements[1].position = float(params.get("scab_mask_pos", 0.72))
    cr.elements[1].color = (0, 0, 0, 1)

    bw = _n(nd, "ShaderNodeRGBToBW", (-120, 0))
    links.new(ramp.outputs["Color"], bw.inputs["Color"])
    warty = bw.outputs["Val"]

    c_base = _rgb_const(nd, _hex_rgba("#FF9E1B"), (180, 100))
    c_scab = _rgb_const(nd, _hex_rgba("#8D7B68"), (180, -60))
    col = _mix_rgba(nd, links, warty, c_base, c_scab, (380, 20))
    links.new(col, bsdf.inputs["Base Color"])

    r_base = _n(nd, "ShaderNodeValue", (380, -120))
    r_base.outputs[0].default_value = 0.4
    r_scab = _n(nd, "ShaderNodeValue", (380, -180))
    r_scab.outputs[0].default_value = 1.0
    rough = _mix_float(nd, links, warty, r_base.outputs[0], r_scab.outputs[0], (500, -140))
    links.new(rough, bsdf.inputs["Roughness"])

    links.new(warty, disp.inputs["Height"])
    disp.inputs["Midlevel"].default_value = 0.0
    disp.inputs["Scale"].default_value = float(params.get("scab_disp_scale", 0.006))
    links.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _assign(obj, mat)
    return mat


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


def apply_preserved_variant(obj, disease: str, disease_params: dict, color_variant: dict):
    """
    원본 GLB 텍스처·재질 유지 → rgb_mul 틴트(healthy 변주) → 병해는 알베도 오버레이.
    """
    from material_preserve import (
        apply_roughness_jitter,
        detach_base_color_socket,
        duplicate_slot_materials,
        fallback_rgb_socket,
        find_output_material,
        find_principled_bsdf,
        multiply_rgb_tint,
    )
    from disease_overlays import (
        overlay_black_spot,
        overlay_canker,
        overlay_greening,
        overlay_scab,
    )

    duplicate_slot_materials(obj)
    dp = disease_params.get(disease, {})
    seen_mat = set()

    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes or id(mat) in seen_mat:
            continue
        seen_mat.add(id(mat))
        nt = mat.node_tree
        nd = nt.nodes
        links = nt.links
        out_nd = find_output_material(nt)
        bsdf = find_principled_bsdf(nt)
        if not bsdf or not out_nd:
            continue

        base_sock = detach_base_color_socket(nt, bsdf)
        if base_sock is None:
            bc = bsdf.inputs["Base Color"]
            base_sock = fallback_rgb_socket(
                nt.nodes,
                tuple(bc.default_value),
                (bsdf.location.x - 520, bsdf.location.y),
            )

        rgba_mul = tuple(color_variant.get("rgb_mul", (1.0, 1.0, 1.0, 1.0)))
        tinted = multiply_rgb_tint(
            nt.nodes,
            links,
            base_sock,
            rgba_mul,
            (bsdf.location.x - 340, bsdf.location.y),
        )
        apply_roughness_jitter(bsdf, float(color_variant.get("roughness_mul", 1.0)))

        x0 = bsdf.location.x

        if disease == "healthy":
            links.new(tinted, bsdf.inputs["Base Color"])
            _zero_displacement(nd, links, out_nd)
            continue

        dispatch = {
            "black_spot": overlay_black_spot,
            "canker": overlay_canker,
            "greening": overlay_greening,
            "scab": overlay_scab,
        }
        fn = dispatch.get(disease)
        if fn is None:
            raise ValueError(f"Unknown disease '{disease}' for preserve pipeline")
        fn(nd, links, bsdf, tinted, dp, out_nd, x0)
