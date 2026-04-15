# src/blender_sim/gltf_material_bake.py
"""
glTF 2.0 / Windows 3D Viewer 호환: 절차적 셰이더는 내보내기 시 Base Color가 끊겨 흰색이 된다.
EMIT 베이크로 알베도를 이미지로 굳인 뒤 Image Texture → Principled BSDF 만 남긴다.

generate_variants.py 트랜스폼 적용 후, export 직전에 호출한다.
"""

from __future__ import annotations

import bpy


def _roughness_fallback(disease: str, disease_params: dict) -> float:
    """공간적으로 다른 거칠기는 버리고, 뷰어용 단일 스칼라."""
    p = disease_params.get(disease) or {}
    if disease == "healthy":
        return float(p.get("roughness", 0.22))
    if disease == "black_spot":
        return 0.52
    if disease == "canker":
        return 0.45
    if disease == "greening":
        return float(p.get("roughness", 0.5))
    if disease == "scab":
        return 0.82
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
    # 섬 간격을 넓혀 EMIT 베이크 시 텍스처 이음새(멀리서 보이는 쪼개짐) 완화
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.08)
    bpy.ops.object.mode_set(mode="OBJECT")


def _find_io_nodes(nt: bpy.types.NodeTree):
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return out, bsdf


def _bake_emit_to_image(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    image_name: str,
    size: int,
) -> bpy.types.Image | None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    # EMIT 알베도 베이크는 낮은 샘플로 충분(고샘플은 병해 노드가 무거울 때 시간만 늘림)
    if hasattr(scene.cycles, "samples"):
        scene.cycles.samples = 12
    if hasattr(scene.render, "bake"):
        # 해상도 대비 넉넉한 픽셀 마진(UV 경계 누출·줄무늬 완화)
        scene.render.bake.margin = max(16, min(64, size // 32))

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


def _build_gltf_safe_material(
    name: str,
    image: bpy.types.Image,
    roughness: float,
    uv_map_name: str | None,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-320, 0)
    tex.image = image

    uv_node = nt.nodes.new("ShaderNodeUVMap")
    uv_node.location = (-620, 0)
    if uv_map_name:
        uv_node.uv_map = uv_map_name

    nt.links.new(uv_node.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
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
) -> None:
    """
    각 메시의 첫 번째 슬롯 재질을 EMIT 베이크 후 단순 PBR로 교체한다.
    """
    rough = _roughness_fallback(disease, disease_params)

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

        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in f"{image_basename}_{obj.name}")[
            :110
        ]
        img = _bake_emit_to_image(obj, mat, safe_name, bake_size)
        if img is None:
            print(f"         [WARN] 베이크 실패 → 단색 폴백: {obj.name}")
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
            b.inputs["Roughness"].default_value = rough
            ntree.links.new(b.outputs["BSDF"], o.inputs["Surface"])
            obj.data.materials[0] = fb
            try:
                bpy.data.materials.remove(mat)
            except Exception:
                pass
            continue

        new_mat = _build_gltf_safe_material(
            f"gltf__{mat.name}",
            img,
            rough,
            uv_name,
        )
        old = mat
        obj.data.materials[0] = new_mat
        try:
            if old.users == 0:
                bpy.data.materials.remove(old)
        except Exception:
            pass
