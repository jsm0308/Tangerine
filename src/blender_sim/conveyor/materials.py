"""
머티리얼: 롤러(고무), 브러시드 알루미늄 레일/모터, 체인 드라이브, 데크.
Blender 버전 간 호환을 위해 Principled 위주로 단순화.
"""

from __future__ import annotations

import bpy


def _principled_bsdf(mat: bpy.types.Material):
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    out.location = (300, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf


def make_rubber_roller_material(name: str = "Mat_RollerRubber") -> bpy.types.Material:
    """짙은 회색 고무, 약한 스펙큘러(공장 상부 조명 반사)."""
    mat = bpy.data.materials.new(name=name)
    _, bsdf = _principled_bsdf(mat)
    bsdf.inputs["Base Color"].default_value = (0.11, 0.11, 0.12, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.86
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.38
    return mat


def make_brushed_aluminum(name: str = "Mat_BrushedAlu") -> bpy.types.Material:
    """사이드 레일·모터 하우징."""
    mat = bpy.data.materials.new(name=name)
    _, bsdf = _principled_bsdf(mat)
    bsdf.inputs["Base Color"].default_value = (0.72, 0.73, 0.75, 1.0)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.36
    return mat


def make_chain_steel(name: str = "Mat_ChainDrive") -> bpy.types.Material:
    """측면 체인 링크 — 어두운 강철."""
    mat = bpy.data.materials.new(name=name)
    _, bsdf = _principled_bsdf(mat)
    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.92
    bsdf.inputs["Roughness"].default_value = 0.48
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.52
    return mat


def make_deck_steel(name: str = "Mat_Deck") -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    _, bsdf = _principled_bsdf(mat)
    bsdf.inputs["Base Color"].default_value = (0.35, 0.36, 0.38, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat
