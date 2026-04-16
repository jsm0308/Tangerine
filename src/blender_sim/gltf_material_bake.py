# src/blender_sim/gltf_material_bake.py
"""
glTF 2.0 / Windows 3D Viewer 호환: 절차적 셰이더는 내보내기 시 Base Color가 끊겨 흰색이 된다.
EMIT 베이크로 알베도·거칠기(그레이)를 굳이고, 선택 시 접선 노멀(지오메트리)을 베이크한다.

generate_variants.py 트랜스폼 적용 후, export 직전에 호출한다.
"""

from __future__ import annotations

import bpy


def _tex_image_colorspace(tex_node: bpy.types.ShaderNodeTexImage, name: str) -> None:
    """Blender 5.x: 색 공간은 노드가 아니라 Image 데이터블록에 둔다."""
    if hasattr(tex_node, "colorspace_settings"):
        tex_node.colorspace_settings.name = name
    elif tex_node.image is not None:
        tex_node.image.colorspace_settings.name = name


def _scalar_roughness_fallback(disease: str, disease_params: dict) -> float:
    """거칠기 맵이 없을 때만 쓰는 단일 스칼라(YAML·질병별 기본)."""
    p = disease_params.get(disease) or {}
    if disease == "healthy":
        return float(p.get("roughness", 0.22))
    if disease == "black_spot":
        base = float((disease_params.get("healthy") or {}).get("roughness", 0.22))
        spot = float(p.get("spot_rough", 0.85))
        return max(base, spot) * 0.55 + min(base, spot) * 0.45
    if disease == "canker":
        return float(p.get("roughness", 0.45))
    if disease == "greening":
        return float(p.get("roughness", 0.5))
    if disease == "scab":
        return float(p.get("roughness", 0.82))
    return 0.5


def _ensure_uv(obj: bpy.types.Object) -> None:
    mesh = obj.data
    if not hasattr(mesh, "uv_layers"):
        return
    if len(mesh.uv_layers) > 0:
        return
    mesh.uv_layers.new(name="UVMap")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.08)
    bpy.ops.object.mode_set(mode="OBJECT")


def _find_io_nodes(nt: bpy.types.NodeTree):
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return out, bsdf


def _configure_cycles_bake(scene: bpy.types.Scene, samples: int, margin: int) -> None:
    scene.render.engine = "CYCLES"
    if hasattr(scene.cycles, "samples"):
        scene.cycles.samples = max(1, int(samples))
    if hasattr(scene.render, "bake"):
        scene.render.bake.margin = max(2, int(margin))


def _bake_emit_to_image(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    image_name: str,
    size: int,
    *,
    samples: int = 96,
    margin: int | None = None,
) -> bpy.types.Image | None:
    m = margin if margin is not None else max(16, min(64, size // 32))
    scene = bpy.context.scene
    _configure_cycles_bake(scene, samples, m)

    nt = mat.node_tree
    out, bsdf = _find_io_nodes(nt)
    if not out or not bsdf:
        return None

    img = bpy.data.images.new(image_name, width=size, height=size, alpha=True)
    img.colorspace_settings.name = "sRGB"

    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    tex_node.select = True
    nt.nodes.active = tex_node

    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.0
    bc_in = bsdf.inputs["Base Color"]
    if bc_in.links:
        nt.links.new(bc_in.links[0].from_socket, emit.inputs["Color"])
    else:
        emit.inputs["Color"].default_value = bc_in.default_value

    surf_in = out.inputs["Surface"]
    if not surf_in.links:
        nt.nodes.remove(emit)
        bpy.data.images.remove(img)
        nt.nodes.remove(tex_node)
        return None
    old_link = surf_in.links[0]
    old_from = old_link.from_socket
    nt.links.remove(old_link)
    nt.links.new(emit.outputs["Emission"], surf_in)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    try:
        bpy.ops.object.bake(type="EMIT")
    except Exception:
        nt.links.remove(surf_in.links[0])
        nt.links.new(old_from, surf_in)
        nt.nodes.remove(emit)
        bpy.data.images.remove(img)
        nt.nodes.remove(tex_node)
        return None

    nt.links.remove(surf_in.links[0])
    nt.links.new(old_from, surf_in)
    nt.nodes.remove(emit)
    nt.nodes.remove(tex_node)

    try:
        img.pack()
    except Exception:
        pass
    return img


def _roughness_socket_to_grey_emit(nt, bsdf, emit, links) -> bool:
    """Roughness 입력을 회색 RGB로 방출(0~1)."""
    r_in = bsdf.inputs["Roughness"]
    if r_in.links:
        src = r_in.links[0].from_socket
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        comb.location = (emit.location[0] - 220, emit.location[1] - 40)
        for axis in ("X", "Y", "Z"):
            if axis in comb.inputs:
                links.new(src, comb.inputs[axis])
        out = comb.outputs.get("Vector") or comb.outputs[0]
        links.new(out, emit.inputs["Color"])
        return True
    v = float(r_in.default_value)
    emit.inputs["Color"].default_value = (v, v, v, 1.0)
    return True


def _bake_roughness_emit(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    image_name: str,
    size: int,
    *,
    samples: int = 96,
    margin: int | None = None,
) -> bpy.types.Image | None:
    """Principled Roughness(공간 변조 포함)를 EMIT로 그레이 베이크."""
    m = margin if margin is not None else max(16, min(64, size // 32))
    scene = bpy.context.scene
    _configure_cycles_bake(scene, samples, m)

    nt = mat.node_tree
    out, bsdf = _find_io_nodes(nt)
    if not out or not bsdf:
        return None

    img = bpy.data.images.new(image_name, width=size, height=size, alpha=True)
    img.colorspace_settings.name = "Non-Color"

    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    tex_node.select = True
    nt.nodes.active = tex_node

    emit = nt.nodes.new("ShaderNodeEmission")
    emit.location = (out.location[0] - 280, out.location[1] - 120)
    emit.inputs["Strength"].default_value = 1.0
    _roughness_socket_to_grey_emit(nt, bsdf, emit, nt.links)

    surf_in = out.inputs["Surface"]
    if not surf_in.links:
        nt.nodes.remove(emit)
        bpy.data.images.remove(img)
        nt.nodes.remove(tex_node)
        return None
    old_link = surf_in.links[0]
    old_from = old_link.from_socket
    nt.links.remove(old_link)
    nt.links.new(emit.outputs["Emission"], surf_in)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    try:
        bpy.ops.object.bake(type="EMIT")
    except Exception:
        nt.links.remove(surf_in.links[0])
        nt.links.new(old_from, surf_in)
        nt.nodes.remove(emit)
        bpy.data.images.remove(img)
        nt.nodes.remove(tex_node)
        return None

    nt.links.remove(surf_in.links[0])
    nt.links.new(old_from, surf_in)
    nt.nodes.remove(emit)
    nt.nodes.remove(tex_node)

    try:
        img.pack()
    except Exception:
        pass
    return img


def _try_bake_native_roughness(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    image_name: str,
    size: int,
    *,
    samples: int,
    margin: int,
) -> bpy.types.Image | None:
    """Blender 4.1+ ROUGHNESS 패스(있으면 EMIT보다 정확). 없으면 None."""
    scene = bpy.context.scene
    _configure_cycles_bake(scene, samples, margin)

    nt = mat.node_tree
    out, _bsdf = _find_io_nodes(nt)
    if not out:
        return None

    img = bpy.data.images.new(image_name, width=size, height=size, alpha=True)
    img.colorspace_settings.name = "Non-Color"

    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    tex_node.select = True
    nt.nodes.active = tex_node

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    try:
        bpy.ops.object.bake(type="ROUGHNESS")
    except Exception:
        bpy.data.images.remove(img)
        nt.nodes.remove(tex_node)
        return None

    nt.nodes.remove(tex_node)
    try:
        img.pack()
    except Exception:
        pass
    return img


def _bake_normal_tangent(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    image_name: str,
    size: int,
    *,
    samples: int = 1,
    margin: int | None = None,
) -> bpy.types.Image | None:
    """접선 공간 지오메트리 노멀(셰이더 범프는 미포함). 부드러운 구에선 거의 평탄."""
    m = margin if margin is not None else max(16, min(64, size // 32))
    scene = bpy.context.scene
    _configure_cycles_bake(scene, max(1, samples), m)

    nt = mat.node_tree
    out, _bsdf = _find_io_nodes(nt)
    if not out:
        return None

    img = bpy.data.images.new(image_name, width=size, height=size, alpha=True)
    img.colorspace_settings.name = "Non-Color"

    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    tex_node.select = True
    nt.nodes.active = tex_node

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    try:
        kw = {"type": "NORMAL", "normal_space": "TANGENT"}
        bpy.ops.object.bake(**kw)
    except TypeError:
        try:
            bpy.ops.object.bake(type="NORMAL")
        except Exception:
            bpy.data.images.remove(img)
            nt.nodes.remove(tex_node)
            return None
    except Exception:
        bpy.data.images.remove(img)
        nt.nodes.remove(tex_node)
        return None

    nt.nodes.remove(tex_node)
    try:
        img.pack()
    except Exception:
        pass
    return img


def _build_gltf_safe_material(
    name: str,
    albedo: bpy.types.Image,
    *,
    roughness_tex: bpy.types.Image | None = None,
    normal_tex: bpy.types.Image | None = None,
    roughness_scalar: float = 0.5,
    uv_map_name: str | None = None,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (520, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (180, 0)

    uv_node = nt.nodes.new("ShaderNodeUVMap")
    uv_node.location = (-700, 120)
    if uv_map_name:
        uv_node.uv_map = uv_map_name

    tex_bc = nt.nodes.new("ShaderNodeTexImage")
    tex_bc.location = (-380, 140)
    tex_bc.image = albedo
    nt.links.new(uv_node.outputs["UV"], tex_bc.inputs["Vector"])
    nt.links.new(tex_bc.outputs["Color"], bsdf.inputs["Base Color"])

    if roughness_tex is not None:
        tex_r = nt.nodes.new("ShaderNodeTexImage")
        tex_r.location = (-380, -120)
        tex_r.image = roughness_tex
        _tex_image_colorspace(tex_r, "Non-Color")
        nt.links.new(uv_node.outputs["UV"], tex_r.inputs["Vector"])
        try:
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            sep.location = (-120, -100)
            if hasattr(sep, "mode"):
                sep.mode = "RGB"
            nt.links.new(tex_r.outputs["Color"], sep.inputs["Color"])
            r_out = sep.outputs.get("Red") or sep.outputs[0]
        except Exception:
            sep = nt.nodes.new("ShaderNodeSeparateRGB")
            sep.location = (-120, -100)
            rin = sep.inputs.get("Color") or sep.inputs.get("Image") or sep.inputs[0]
            nt.links.new(tex_r.outputs["Color"], rin)
            r_out = sep.outputs.get("R") or sep.outputs.get("Red") or sep.outputs[0]
        nt.links.new(r_out, bsdf.inputs["Roughness"])
        bsdf.inputs["Roughness"].default_value = 1.0
    else:
        bsdf.inputs["Roughness"].default_value = roughness_scalar

    if normal_tex is not None:
        tex_n = nt.nodes.new("ShaderNodeTexImage")
        tex_n.location = (-380, -360)
        tex_n.image = normal_tex
        _tex_image_colorspace(tex_n, "Non-Color")
        nt.links.new(uv_node.outputs["UV"], tex_n.inputs["Vector"])
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-80, -320)
        nm.inputs["Strength"].default_value = 1.0
        nt.links.new(tex_n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.5
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.5
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def simplify_materials_for_gltf_export(
    mesh_objects: list,
    disease: str,
    disease_params: dict,
    *,
    bake_size: int = 1024,
    image_basename: str = "bake_bc",
    bake_samples: int = 96,
    bake_margin: int | None = None,
    bake_roughness: bool = True,
    bake_normal: bool = True,
    prefer_native_roughness: bool = True,
) -> None:
    """
    각 메시의 첫 번째 슬롯 재질을 알베도 EMIT 베이크 후 단순 PBR로 교체한다.
    선택적으로 거칠기(그레이)·접선 노멀을 추가한다.
    """
    rough_fb = _scalar_roughness_fallback(disease, disease_params)
    margin = bake_margin if bake_margin is not None else max(16, min(64, bake_size // 32))

    for obj in mesh_objects:
        if obj.type != "MESH":
            continue
        if not obj.data.materials:
            continue
        mat = obj.data.materials[0]
        if not mat or not mat.use_nodes:
            continue

        _ensure_uv(obj)
        uv_name = obj.data.uv_layers.active.name if obj.data.uv_layers else None

        base_safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in f"{image_basename}_{obj.name}")[:110]

        img_bc = _bake_emit_to_image(
            obj, mat, f"{base_safe}_bc", bake_size, samples=bake_samples, margin=margin
        )
        if img_bc is None:
            print(f"         [WARN] 알베도 베이크 실패 → 단색 폴백: {obj.name}")
            p = disease_params.get(disease) or {}
            rgba = (0.85, 0.35, 0.05, 1.0)
            if disease == "healthy" and "base_color" in p:
                rgba = tuple(p["base_color"])
            elif "base_color" in p:
                rgba = tuple(p["base_color"])
            elif disease == "greening" and "orange_color" in p:
                rgba = tuple(p["orange_color"])
            fb = bpy.data.materials.new(name=f"gltf_fb__{obj.name}")
            fb.use_nodes = True
            ntree = fb.node_tree
            ntree.nodes.clear()
            o = ntree.nodes.new("ShaderNodeOutputMaterial")
            b = ntree.nodes.new("ShaderNodeBsdfPrincipled")
            b.inputs["Base Color"].default_value = rgba
            b.inputs["Roughness"].default_value = rough_fb
            ntree.links.new(b.outputs["BSDF"], o.inputs["Surface"])
            obj.data.materials[0] = fb
            try:
                bpy.data.materials.remove(mat)
            except Exception:
                pass
            continue

        img_rough = None
        if bake_roughness:
            if prefer_native_roughness:
                img_rough = _try_bake_native_roughness(
                    obj,
                    mat,
                    f"{base_safe}_rough",
                    bake_size,
                    samples=bake_samples,
                    margin=margin,
                )
            if img_rough is None:
                img_rough = _bake_roughness_emit(
                    obj,
                    mat,
                    f"{base_safe}_rough",
                    bake_size,
                    samples=bake_samples,
                    margin=margin,
                )
            if img_rough is None:
                print(f"         [WARN] 거칠기 베이크 실패 → 스칼라만: {obj.name}")

        img_nrm = None
        if bake_normal:
            img_nrm = _bake_normal_tangent(
                obj, mat, f"{base_safe}_nrm", bake_size, samples=1, margin=margin
            )
            if img_nrm is None:
                print(f"         [WARN] 노멀 베이크 생략/실패: {obj.name}")

        new_mat = _build_gltf_safe_material(
            f"gltf__{mat.name}",
            img_bc,
            roughness_tex=img_rough,
            normal_tex=img_nrm,
            roughness_scalar=rough_fb,
            uv_map_name=uv_name,
        )
        old = mat
        obj.data.materials[0] = new_mat
        try:
            if old.users == 0:
                bpy.data.materials.remove(old)
        except Exception:
            pass
