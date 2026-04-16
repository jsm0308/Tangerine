# src/blender_sim/disease_overlays.py
"""원본 알베도(틴트 적용 후 socket) 위에 병해 절차 레이어를 얹는다."""

from __future__ import annotations

# Re-use helpers from disease_materials (same module cluster)
from disease_materials import (
    _hex_rgba,
    _mix_float,
    _mix_rgba,
    _n,
    _noise_scalar_out,
    _rgb_const,
    _vor_metric_euclidean,
    _zero_displacement,
)


def overlay_black_spot(nd, links, bsdf, tinted_base_sock, params: dict, out_nd, x0: float):
    tc = _n(nd, "ShaderNodeTexCoord", (x0 - 800, 0))
    # 좌표 워프: 규격 격자·후추 느낌 완화
    warp_n = _n(nd, "ShaderNodeTexNoise", (x0 - 720, -200))
    warp_n.inputs["Scale"].default_value = float(params.get("spot_warp_noise_scale", 14.0))
    warp_n.inputs["Detail"].default_value = float(params.get("spot_warp_detail", 4.0))
    warp_n.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], warp_n.inputs["Vector"])
    w_amp = _n(nd, "ShaderNodeValue", (x0 - 720, -320))
    w_amp.outputs[0].default_value = float(params.get("spot_warp_strength", 0.045))
    w_bw = _n(nd, "ShaderNodeRGBToBW", (x0 - 560, -280))
    links.new(warp_n.outputs["Color"], w_bw.inputs["Color"])
    w_scl = _n(nd, "ShaderNodeMath", (x0 - 560, -260))
    w_scl.operation = "MULTIPLY"
    links.new(w_bw.outputs["Val"], w_scl.inputs[0])
    links.new(w_amp.outputs[0], w_scl.inputs[1])
    w_xyz = _n(nd, "ShaderNodeCombineXYZ", (x0 - 440, -240))
    for axis in ("X", "Y", "Z"):
        if axis in w_xyz.inputs:
            links.new(w_scl.outputs[0], w_xyz.inputs[axis])
    wadd = _n(nd, "ShaderNodeVectorMath", (x0 - 320, -120))
    wadd.operation = "ADD"
    links.new(tc.outputs["Object"], wadd.inputs[0])
    wv = w_xyz.outputs.get("Vector") or w_xyz.outputs[0]
    links.new(wv, wadd.inputs[1])
    vec_for_vor = wadd.outputs["Vector"]

    vor = _n(nd, "ShaderNodeTexVoronoi", (x0 - 560, 0))
    ramp = _n(nd, "ShaderNodeValToRGB", (x0 - 320, 0))
    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    _vor_metric_euclidean(vor)
    vor.inputs["Scale"].default_value = float(params.get("voronoi_scale", 175.0))
    if "Randomness" in vor.inputs:
        vor.inputs["Randomness"].default_value = float(params.get("voronoi_randomness", 0.92))
    if "Smoothness" in vor.inputs:
        vor.inputs["Smoothness"].default_value = float(params.get("voronoi_smooth", 0.88))
    links.new(vec_for_vor, vor.inputs["Vector"])
    dist_f1 = vor.outputs.get("Distance") or vor.outputs[1]

    use_f2f1 = bool(params.get("spot_use_f2_minus_f1", True))
    if use_f2f1:
        vor2 = _n(nd, "ShaderNodeTexVoronoi", (x0 - 560, 140))
        vor2.voronoi_dimensions = "3D"
        vor2.feature = "F2"
        _vor_metric_euclidean(vor2)
        vor2.inputs["Scale"].default_value = float(params.get("voronoi_scale", 175.0))
        if "Randomness" in vor2.inputs:
            vor2.inputs["Randomness"].default_value = float(params.get("voronoi_randomness", 0.92))
        if "Smoothness" in vor2.inputs:
            vor2.inputs["Smoothness"].default_value = float(params.get("voronoi_smooth", 0.88))
        links.new(vec_for_vor, vor2.inputs["Vector"])
        dist_f2 = vor2.outputs.get("Distance") or vor2.outputs[1]
        df = _n(nd, "ShaderNodeMath", (x0 - 400, 80))
        df.operation = "SUBTRACT"
        df.use_clamp = False
        links.new(dist_f2, df.inputs[0])
        links.new(dist_f1, df.inputs[1])
        absm = _n(nd, "ShaderNodeMath", (x0 - 400, 20))
        absm.operation = "ABSOLUTE"
        links.new(df.outputs[0], absm.inputs[0])
        dist_sock = absm.outputs[0]
        f2f1_scale = float(params.get("spot_f2f1_map_scale", 2.8))
        dmap = _n(nd, "ShaderNodeMapRange", (x0 - 380, 0))
        dmap.inputs["From Min"].default_value = 0.0
        dmap.inputs["From Max"].default_value = float(params.get("spot_dist_map_max", 0.18)) * f2f1_scale
    else:
        dist_sock = dist_f1
        dmap = _n(nd, "ShaderNodeMapRange", (x0 - 380, 0))
        dmap.inputs["From Min"].default_value = 0.0
        dmap.inputs["From Max"].default_value = float(params.get("spot_dist_map_max", 0.18))
    dmap.inputs["To Min"].default_value = 0.0
    dmap.inputs["To Max"].default_value = 1.0
    if hasattr(dmap, "use_clamp"):
        dmap.use_clamp = True
    links.new(dist_sock, dmap.inputs["Value"])
    links.new(dmap.outputs["Result"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    # LINEAR: 부드러운 반점 경계(격자 쪼개짐·과한 계단 완화). spot_ramp_pos = 암색이 강해지기 시작하는 구간 끝.
    cr.interpolation = str(params.get("spot_ramp_interpolation", "LINEAR"))
    cr.elements[0].position = 0.0
    cr.elements[0].color = (1, 1, 1, 1)
    cr.elements[1].position = float(params.get("spot_ramp_pos", 0.28))
    dark = _hex_rgba(str(params.get("spot_color_hex", "#0A0605")))
    cr.elements[1].color = (*dark[:3], 1.0)
    bw = _n(nd, "ShaderNodeRGBToBW", (x0 - 120, 40))
    links.new(ramp.outputs["Color"], bw.inputs["Color"])
    spot_raw = bw.outputs["Val"]
    boost_v = _n(nd, "ShaderNodeValue", (x0 + 40, -20))
    boost_v.outputs[0].default_value = float(params.get("spot_mix_boost", 1.2))
    boosted = _n(nd, "ShaderNodeMath", (x0 + 160, 20))
    boosted.operation = "MULTIPLY"
    boosted.use_clamp = True
    links.new(spot_raw, boosted.inputs[0])
    links.new(boost_v.outputs[0], boosted.inputs[1])
    spot_mask = boosted.outputs[0]
    c_dark = _rgb_const(nd, _hex_rgba(str(params.get("spot_dark_hex", "#050302"))), (x0 + 180, -40))
    col = _mix_rgba(nd, links, spot_mask, tinted_base_sock, c_dark, (x0 + 380, 60))
    links.new(col, bsdf.inputs["Base Color"])

    r_lo = _n(nd, "ShaderNodeValue", (x0 + 380, -80))
    r_hi = _n(nd, "ShaderNodeValue", (x0 + 380, -140))
    r_lo.outputs[0].default_value = bsdf.inputs["Roughness"].default_value
    r_hi.outputs[0].default_value = max(r_lo.outputs[0].default_value, float(params.get("spot_rough", 0.85)))
    if not bsdf.inputs["Roughness"].links:
        rough = _mix_float(nd, links, spot_mask, r_lo.outputs[0], r_hi.outputs[0], (x0 + 500, -100))
        links.new(rough, bsdf.inputs["Roughness"])

    noise = _n(nd, "ShaderNodeTexNoise", (x0 - 200, -280))
    noise.inputs["Scale"].default_value = 250.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.65
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nsc = _noise_scalar_out(noise)
    bump_n = _n(nd, "ShaderNodeBump", (x0 + 420, -220))
    mul_b = _n(nd, "ShaderNodeMath", (x0 + 200, -200))
    mul_b.operation = "MULTIPLY"
    links.new(spot_mask, mul_b.inputs[0])
    links.new(nsc, mul_b.inputs[1])
    bump_n.inputs["Strength"].default_value = float(params.get("overlay_bump_strength", 0.14))
    bump_n.inputs["Distance"].default_value = 0.001
    links.new(mul_b.outputs[0], bump_n.inputs["Height"])
    if not bsdf.inputs["Normal"].links:
        links.new(bump_n.outputs["Normal"], bsdf.inputs["Normal"])
    _zero_displacement(nd, links, out_nd)


def overlay_canker(nd, links, bsdf, tinted_base_sock, params: dict, out_nd, x0: float):
    tc = _n(nd, "ShaderNodeTexCoord", (x0 - 900, 0))
    vor = _n(nd, "ShaderNodeTexVoronoi", (x0 - 660, 0))
    r_col = _n(nd, "ShaderNodeValToRGB", (x0 - 400, 120))
    vor.voronoi_dimensions = "3D"
    vor.feature = "DISTANCE_TO_EDGE"
    _vor_metric_euclidean(vor)
    vor.inputs["Scale"].default_value = float(params.get("lesion_scale", 25.0))
    if "Randomness" in vor.inputs:
        vor.inputs["Randomness"].default_value = 0.45
    links.new(tc.outputs["Object"], vor.inputs["Vector"])
    de = vor.outputs.get("Distance") or vor.outputs[1]
    dem = _n(nd, "ShaderNodeMapRange", (x0 - 520, 0))
    dem.inputs["From Min"].default_value = 0.0
    dem.inputs["From Max"].default_value = float(params.get("canker_de_span", 0.30))
    dem.inputs["To Min"].default_value = 0.0
    dem.inputs["To Max"].default_value = 1.0
    if hasattr(dem, "use_clamp"):
        dem.use_clamp = True
    links.new(de, dem.inputs["Value"])
    de_n = dem.outputs["Result"]
    links.new(de_n, r_col.inputs["Fac"])
    c0 = r_col.color_ramp
    c0.interpolation = "EASE"
    c0.elements[0].position = 0.0
    c0.elements[0].color = _hex_rgba("#6B4E31")
    c0.elements[1].position = 0.1
    c0.elements[1].color = _hex_rgba("#F9E076")
    elc = c0.elements.new(0.22)
    elc.color = _hex_rgba("#FF9E1B")

    m = _n(nd, "ShaderNodeMapRange", (x0 - 220, 60))
    m.inputs["From Min"].default_value = float(params.get("canker_overlay_in", 0.0))
    m.inputs["From Max"].default_value = float(params.get("canker_overlay_out", 0.38))
    m.inputs["To Min"].default_value = 0.0
    m.inputs["To Max"].default_value = 1.0
    if hasattr(m, "use_clamp"):
        m.use_clamp = True
    links.new(de_n, m.inputs["Value"])
    lesion_mask = m.outputs["Result"]

    str_n = _n(nd, "ShaderNodeValue", (x0 + 40, 120))
    str_n.outputs[0].default_value = float(params.get("overlay_strength", 0.88))
    mul_m = _n(nd, "ShaderNodeMath", (x0 + 120, 100))
    mul_m.operation = "MULTIPLY"
    links.new(lesion_mask, mul_m.inputs[0])
    links.new(str_n.outputs[0], mul_m.inputs[1])

    final = _mix_rgba(nd, links, mul_m.outputs[0], tinted_base_sock, r_col.outputs["Color"], (x0 + 260, 80))
    links.new(final, bsdf.inputs["Base Color"])

    r_rough = _n(nd, "ShaderNodeValToRGB", (x0 - 400, -40))
    links.new(de_n, r_rough.inputs["Fac"])
    g0 = r_rough.color_ramp
    g0.interpolation = "EASE"
    g0.elements[0].position = 0.0
    g0.elements[0].color = (0.95, 0.95, 0.95, 1)
    g0.elements[1].position = 0.1
    g0.elements[1].color = (0.15, 0.15, 0.15, 1)
    elg = g0.elements.new(0.22)
    elg.color = (0.3, 0.3, 0.3, 1)
    bw_r = _n(nd, "ShaderNodeRGBToBW", (x0 + 520, -20))
    links.new(r_rough.outputs["Color"], bw_r.inputs["Color"])
    if not bsdf.inputs["Roughness"].links:
        r_def = _n(nd, "ShaderNodeValue", (x0 + 520, -80))
        r_def.outputs[0].default_value = bsdf.inputs["Roughness"].default_value
        rough = _mix_float(nd, links, mul_m.outputs[0], r_def.outputs[0], bw_r.outputs["Val"], (x0 + 640, -40))
        links.new(rough, bsdf.inputs["Roughness"])

    r_hgt = _n(nd, "ShaderNodeValToRGB", (x0 - 400, -220))
    links.new(de_n, r_hgt.inputs["Fac"])
    h0 = r_hgt.color_ramp
    h0.interpolation = "CONSTANT"
    h0.elements[0].position = 0.0
    h0.elements[0].color = (0.0, 0.0, 0.0, 1)
    h0.elements[1].position = 0.08
    h0.elements[1].color = (0.5, 0.0, 0.0, 1)
    h0.elements.new(0.18).color = (1.0, 0.0, 0.0, 1)
    mr = _n(nd, "ShaderNodeMapRange", (x0 + 420, -240))
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = -0.002
    mr.inputs["To Max"].default_value = 0.003
    bw_h = _n(nd, "ShaderNodeRGBToBW", (x0 + 240, -220))
    links.new(r_hgt.outputs["Color"], bw_h.inputs["Color"])
    links.new(bw_h.outputs["Val"], mr.inputs["Value"])
    disp = _n(nd, "ShaderNodeDisplacement", (x0 + 620, -300))
    links.new(mr.outputs["Result"], disp.inputs["Height"])
    disp.inputs["Scale"].default_value = float(params.get("disp_scale", 1.0))
    disp.inputs["Midlevel"].default_value = 0.0
    links.new(disp.outputs["Displacement"], out_nd.inputs["Displacement"])


def overlay_greening(nd, links, bsdf, tinted_base_sock, params: dict, out_nd, x0: float):
    tc = _n(nd, "ShaderNodeTexCoord", (x0 - 820, 0))
    mus = _n(nd, "ShaderNodeTexNoise", (x0 - 580, 120))
    nz = _n(nd, "ShaderNodeTexNoise", (x0 - 580, -80))
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
    mix_n = _n(nd, "ShaderNodeMixRGB", (x0 - 420, 20))
    mix_n.blend_type = "MIX"
    mix_n.inputs["Fac"].default_value = 0.5
    links.new(mus.outputs["Color"], mix_n.inputs["Color1"])
    links.new(nz.outputs["Color"], mix_n.inputs["Color2"])
    ramp_m = _n(nd, "ShaderNodeValToRGB", (x0 - 340, 40))
    links.new(mix_n.outputs["Color"], ramp_m.inputs["Fac"])
    rm = ramp_m.color_ramp
    rm.interpolation = "EASE"
    rm.elements[0].position = float(params.get("mottle_ramp_lo", 0.2))
    rm.elements[0].color = (0, 0, 0, 1)
    rm.elements[1].position = float(params.get("mottle_ramp_hi", 0.78))
    rm.elements[1].color = (1, 1, 1, 1)
    sep = _n(nd, "ShaderNodeSeparateXYZ", (x0 - 580, -280))
    grad = _n(nd, "ShaderNodeMapRange", (x0 - 360, -260))
    links.new(tc.outputs["Object"], sep.inputs["Vector"])
    grad.inputs["From Min"].default_value = -1.0
    grad.inputs["From Max"].default_value = 0.35
    grad.inputs["To Min"].default_value = 1.0
    grad.inputs["To Max"].default_value = 0.0
    if hasattr(grad, "use_clamp"):
        grad.use_clamp = True
    links.new(sep.outputs["Z"], grad.inputs["Value"])
    mottle = _n(nd, "ShaderNodeRGBToBW", (x0 - 200, 40))
    links.new(ramp_m.outputs["Color"], mottle.inputs["Color"])
    comb = _n(nd, "ShaderNodeMath", (x0 - 40, -80))
    comb.operation = "MULTIPLY"
    links.new(mottle.outputs["Val"], comb.inputs[0])
    links.new(grad.outputs["Result"], comb.inputs[1])
    # HLB 느낌: 황록·올리브·녹색이 베이스 오렌지를 덮도록 색을 명확히 녹색 쪽으로 잡는다.
    c_yellow = _rgb_const(nd, _hex_rgba(str(params.get("greening_yellow_hex", "#A4C060"))), (x0 + 120, 180))
    c_olive = _rgb_const(nd, _hex_rgba(str(params.get("greening_olive_hex", "#4A7D3E"))), (x0 + 120, 20))
    c_orange = _rgb_const(nd, _hex_rgba(str(params.get("greening_orange_hex", "#E88A28"))), (x0 + 120, -140))
    c_green = _rgb_const(nd, _hex_rgba(str(params.get("green_tint_hex", "#2F6A38"))), (x0 + 120, -300))
    mx1 = _mix_rgba(nd, links, mottle.outputs["Val"], c_orange, c_yellow, (x0 + 300, 100))
    mx2 = _mix_rgba(nd, links, comb.outputs[0], mx1, c_olive, (x0 + 480, 40))
    # 전역 녹색 기운(시인성 확보)
    green_lean = _n(nd, "ShaderNodeMath", (x0 + 620, -120))
    green_lean.operation = "MULTIPLY"
    links.new(mottle.outputs["Val"], green_lean.inputs[0])
    links.new(comb.outputs[0], green_lean.inputs[1])
    mx3 = _mix_rgba(nd, links, green_lean.outputs[0], mx2, c_green, (x0 + 660, -40))

    ost = _n(nd, "ShaderNodeValue", (x0 + 600, 40))
    ost.outputs[0].default_value = float(params.get("overlay_strength", 0.88))
    gboost = _n(nd, "ShaderNodeValue", (x0 + 600, 100))
    gboost.outputs[0].default_value = float(params.get("greening_boost", 1.25))
    blend = _n(nd, "ShaderNodeMath", (x0 + 700, 40))
    blend.operation = "MULTIPLY"
    blend.use_clamp = True
    links.new(mottle.outputs["Val"], blend.inputs[0])
    links.new(ost.outputs[0], blend.inputs[1])
    blend2 = _n(nd, "ShaderNodeMath", (x0 + 760, 40))
    blend2.operation = "MULTIPLY"
    blend2.use_clamp = True
    links.new(blend.outputs[0], blend2.inputs[0])
    links.new(gboost.outputs[0], blend2.inputs[1])
    final = _mix_rgba(nd, links, blend2.outputs[0], tinted_base_sock, mx3, (x0 + 900, 40))
    links.new(final, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = float(params.get("roughness", 0.5))
    _zero_displacement(nd, links, out_nd)


def overlay_scab(nd, links, bsdf, tinted_base_sock, params: dict, out_nd, x0: float):
    tc = _n(nd, "ShaderNodeTexCoord", (x0 - 800, 0))
    n1 = _n(nd, "ShaderNodeTexNoise", (x0 - 560, 80))
    n2 = _n(nd, "ShaderNodeTexNoise", (x0 - 560, -100))
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
    mix_w = _n(nd, "ShaderNodeMixRGB", (x0 - 420, -20))
    mix_w.inputs["Fac"].default_value = 0.55
    links.new(n1.outputs["Color"], mix_w.inputs["Color1"])
    links.new(n2.outputs["Color"], mix_w.inputs["Color2"])
    ramp = _n(nd, "ShaderNodeValToRGB", (x0 - 300, 0))
    links.new(mix_w.outputs["Color"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (1, 1, 1, 1)
    cr.elements[1].position = float(params.get("scab_mask_pos", 0.72))
    cr.elements[1].color = (0, 0, 0, 1)
    bw = _n(nd, "ShaderNodeRGBToBW", (x0 - 120, 0))
    links.new(ramp.outputs["Color"], bw.inputs["Color"])
    warty = bw.outputs["Val"]
    c_scab = _rgb_const(nd, _hex_rgba("#8D7B68"), (x0 + 180, -60))
    ost = _n(nd, "ShaderNodeValue", (x0 + 300, 0))
    ost.outputs[0].default_value = float(params.get("overlay_strength", 0.78))
    wm = _n(nd, "ShaderNodeMath", (x0 + 160, -40))
    wm.operation = "MULTIPLY"
    links.new(warty, wm.inputs[0])
    links.new(ost.outputs[0], wm.inputs[1])
    col = _mix_rgba(nd, links, wm.outputs[0], tinted_base_sock, c_scab, (x0 + 380, 20))
    links.new(col, bsdf.inputs["Base Color"])
    r_lo = _n(nd, "ShaderNodeValue", (x0 + 380, -120))
    r_hi = _n(nd, "ShaderNodeValue", (x0 + 380, -180))
    r_lo.outputs[0].default_value = bsdf.inputs["Roughness"].default_value
    r_hi.outputs[0].default_value = 1.0
    if not bsdf.inputs["Roughness"].links:
        rough = _mix_float(nd, links, wm.outputs[0], r_lo.outputs[0], r_hi.outputs[0], (x0 + 500, -140))
        links.new(rough, bsdf.inputs["Roughness"])
    disp = _n(nd, "ShaderNodeDisplacement", (x0 + 500, -280))
    links.new(warty, disp.inputs["Height"])
    disp.inputs["Midlevel"].default_value = 0.0
    disp.inputs["Scale"].default_value = float(params.get("scab_disp_scale", 0.006))
    links.new(disp.outputs["Displacement"], out_nd.inputs["Displacement"])
