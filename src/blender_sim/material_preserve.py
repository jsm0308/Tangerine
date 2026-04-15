# src/blender_sim/material_preserve.py
"""
원본 GLB의 Principled 재질·텍스처를 유지한 채 healthy 틴트 후 병해를 알베도 위에 오버레이한다.
"""

from __future__ import annotations

import bpy


def find_output_material(nt: bpy.types.NodeTree):
    for n in nt.nodes:
        if n.type == "OUTPUT_MATERIAL":
            return n
    return None


def find_principled_bsdf(nt: bpy.types.NodeTree) -> bpy.types.ShaderNode | None:
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def detach_base_color_socket(
    nt: bpy.types.NodeTree, bsdf: bpy.types.ShaderNode
) -> bpy.types.NodeSocket | None:
    sock_in = bsdf.inputs["Base Color"]
    if sock_in.links:
        lk = sock_in.links[0]
        src = lk.from_socket
        nt.links.remove(lk)
        return src
    return None


def fallback_rgb_socket(nodes, rgba: tuple, loc) -> bpy.types.NodeSocket:
    n = nodes.new("ShaderNodeRGB")
    n.location = loc
    n.outputs[0].default_value = rgba
    return n.outputs["Color"]


def multiply_rgb_tint(
    nodes: bpy.types.Nodes,
    links: bpy.types.NodeLinks,
    base_sock: bpy.types.NodeSocket,
    rgba_mul: tuple,
    loc: tuple[float, float],
) -> bpy.types.NodeSocket:
    """Base Color 체인에 RGB 곱 틴트(healthy 변주)."""
    rgb = nodes.new("ShaderNodeRGB")
    rgb.location = (loc[0] - 220, loc[1])
    rgb.outputs[0].default_value = rgba_mul
    try:
        m = nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = "MULTIPLY"
        m.location = loc
        m.inputs["Factor"].default_value = 1.0
        links.new(base_sock, m.inputs["A"])
        links.new(rgb.outputs["Color"], m.inputs["B"])
        return m.outputs["Result"]
    except Exception:
        m = nodes.new("ShaderNodeMixRGB")
        m.blend_type = "MULTIPLY"
        m.location = loc
        m.inputs["Fac"].default_value = 1.0
        links.new(base_sock, m.inputs["Color1"])
        links.new(rgb.outputs["Color"], m.inputs["Color2"])
        return m.outputs["Color"]


def apply_roughness_jitter(bsdf: bpy.types.ShaderNode, mul: float) -> None:
    r_in = bsdf.inputs["Roughness"]
    if r_in.links:
        return
    r_in.default_value = min(1.0, max(0.0, r_in.default_value * mul))


def duplicate_slot_materials(obj: bpy.types.Object) -> None:
    """잡 간 오염 방지: 슬롯마다 material.copy()."""
    for i in range(len(obj.material_slots)):
        slot = obj.material_slots[i]
        if slot.material:
            slot.material = slot.material.copy()
