# src/blender_sim/generate_variants.py
"""
헤드리스 Blender 배치 변종 생성기.

실행:
  blender --background --python src/blender_sim/generate_variants.py \\
          -- --config data/Tangerine_3D/configs/variants_batch.yaml

  # 실제 내보내기 없이 목록만 확인:
  blender --background --python src/blender_sim/generate_variants.py \\
          -- --config data/Tangerine_3D/configs/variants_batch.yaml --dry-run

출력:
  output_name_style short: <base>__<disease>.glb
  output_name_style full:  <base>__<disease>__s<N>__q<N>__h<N>__c<N>.glb
  <output_dir>/manifest.json
  기본 설정은 베이스 GLB 수 × 병해 종 수(예: 3×5 = 15); YAML에서 축 값을 늘리면 그리드 확장.
"""

import bpy
import sys
import os
import json
import random
import argparse
from pathlib import Path

# ─── sys.path: sibling 모듈 import 허용 ──────────────────────────────────────
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from disease_materials import apply_preserved_variant
from gltf_material_bake import simplify_materials_for_gltf_export

# 설정은 (1) --job-json (권장: 래퍼가 YAML→JSON) 또는 (2) --config YAML — 후자는 Blender 내 PyYAML 필요.

# ─── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--job-json", default=None, help="래퍼가 만든 해석된 설정 JSON (PyYAML 불필요)")
    p.add_argument("--config", default="data/Tangerine_3D/configs/variants_batch.yaml")
    p.add_argument("--dry-run", action="store_true", help="내보내기 없이 목록만 출력")
    return p.parse_args(argv)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(p: str | Path) -> Path:
    pp = Path(p)
    if pp.is_absolute():
        return pp
    return _project_root() / pp


# ─── Blender 씬 헬퍼 ─────────────────────────────────────────────────────────

def _clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for blk in list(bpy.data.meshes):
        bpy.data.meshes.remove(blk)
    for blk in list(bpy.data.materials):
        bpy.data.materials.remove(blk)

def _load_glb(path: Path):
    """
    GLB를 import하고 (임포트된 전체, 메시만, 루트만) 튜플을 반환.
    import 전 오브젝트 집합 diff로 신규 오브젝트를 정확히 추출.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported  = [o for o in bpy.data.objects if o not in before]
    mesh_objs = [o for o in imported if o.type == 'MESH']
    # 루트 = 임포트 집합 안에 부모가 없는 오브젝트
    roots     = [o for o in imported if o.parent not in imported]
    return imported, mesh_objs, roots

def _export_glb(out_path: Path, objects: list):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(out_path),
        export_format='GLB',
        use_selection=True,
        export_materials='EXPORT',
    )


# ─── 트랜스폼 ─────────────────────────────────────────────────────────────────

def _apply_transform(roots: list, size: float, squish: dict, height: float):
    """
    루트 오브젝트에만 scale 적용 (자식 오브젝트에 자동으로 cascade).
      size   : uniform scale (크기 변수)
      squish : {'scale_xy': float, 'scale_z': float}  (찌그러짐 변수)
      height : Z-only 추가 배율 (높이 변수)

    최종 scale:
      X = Y = size × squish.scale_xy
      Z     = size × squish.scale_z × height

    glTF 내보내기 안정화를 위해 scale 을 메시에 굳힘(transform_apply).
    """
    sxy = size * squish['scale_xy']
    sz = size * squish['scale_z'] * height
    for obj in roots:
        obj.scale = (sxy, sxy, sz)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in roots:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(scale=True)
        obj.select_set(False)


# ─── 변종 목록 빌더 ───────────────────────────────────────────────────────────

def _axis_values(spec: dict, rng: random.Random) -> list:
    if spec.get("values"):
        return list(spec["values"])
    if spec.get("auto_generate", True):
        lo, hi, n = spec["min"], spec["max"], spec["count"]
        return [round(rng.uniform(lo, hi), 4) for _ in range(n)]
    return list(spec.get("values") or [])


def build_jobs(cfg: dict) -> list:
    rng = random.Random(cfg.get("random_seed", 42))
    size_vals = _axis_values(cfg["size_variants"], rng)
    height_vals = _axis_values(cfg["height_variants"], rng)
    squish_list = cfg["squish_variants"]
    color_list = cfg["color_variants"]
    diseases = list(cfg["disease_params"].keys())
    sources = cfg["glb_sources"]
    name_style = (cfg.get("output_name_style") or "full").strip().lower()

    jobs = []
    for src in sources:
        for si, sv in enumerate(size_vals, 1):
            for qi, sq in enumerate(squish_list, 1):
                for hi, hv in enumerate(height_vals, 1):
                    for ci, cv in enumerate(color_list, 1):
                        for dis in diseases:
                            if name_style == "short":
                                fname = f"{src['name']}__{dis}.glb"
                            else:
                                fname = f"{src['name']}__{dis}__s{si}__q{qi}__h{hi}__c{ci}.glb"
                            jobs.append(
                                {
                                    "base_name": src["name"],
                                    "glb_path": src["path"],
                                    "disease": dis,
                                    "size": sv,
                                    "squish": sq,
                                    "height": hv,
                                    "color_idx": ci,
                                    "color_label": cv.get("label", f"c{ci}"),
                                    "color_variant": cv,
                                    "filename": fname,
                                }
                            )
    if name_style == "short":
        names = [j["filename"] for j in jobs]
        if len(names) != len(set(names)):
            raise ValueError(
                "output_name_style=short 인데 파일명이 겹칩니다. "
                "size/squish/height/color 축을 각각 1값만 쓰거나 output_name_style=full 로 바꾸세요."
            )
    return jobs


# ─── main ─────────────────────────────────────────────────────────────────────

def _load_config(args) -> dict:
    if getattr(args, "job_json", None):
        jp = _resolve_path(args.job_json)
        if not jp.is_file():
            sys.exit(f"[ERROR] job-json 없음: {jp}")
        with open(jp, "r", encoding="utf-8") as f:
            return json.load(f)
    config_path = _resolve_path(args.config)
    if not config_path.is_file():
        sys.exit(f"[ERROR] 설정 파일 없음: {config_path}")
    if config_path.suffix.lower() == ".json":
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        import yaml  # type: ignore
    except ImportError:
        sys.exit(
            "[ERROR] PyYAML 없음. `python scripts/generate_variants_build.py` 로 실행하거나 "
            "Blender Python에: pip install pyyaml"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    args = _parse_args()

    cfg = _load_config(args)

    out_dir = _resolve_path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    for src in cfg.get("glb_sources") or []:
        src["path"] = str(_resolve_path(src["path"]))

    jobs = build_jobs(cfg)
    total = len(jobs)
    print(f"[Tangerine] {total}개 변종 → {out_dir}")

    if args.dry_run:
        for j in jobs:
            print(f"  DRY-RUN  {j['filename']}")
        print(f"[Tangerine] dry-run 완료. {total}개 목록만 출력.")
        return

    manifest = []

    for idx, job in enumerate(jobs, 1):
        print(f"[{idx:>4}/{total}] {job['filename']}")

        glb_path = Path(job['glb_path'])
        if not glb_path.exists():
            print(f"         [SKIP] GLB 없음: {glb_path}")
            continue

        _clear_scene()
        imported, mesh_objs, roots = _load_glb(glb_path)

        if not mesh_objs:
            print(f"         [SKIP] 메시 오브젝트 없음")
            continue

        bpy.ops.object.select_all(action="DESELECT")
        for mobj in mesh_objs:
            mobj.select_set(True)
            bpy.context.view_layer.objects.active = mobj
            bpy.ops.object.shade_smooth()
            mobj.select_set(False)

        # 원본 healthy 재질 유지 → 틴트 → 병해 오버레이
        for mobj in mesh_objs:
            apply_preserved_variant(
                mobj,
                job["disease"],
                cfg["disease_params"],
                job["color_variant"],
            )

        # 트랜스폼 적용 (루트 없으면 메시 직접 사용)
        _apply_transform(
            roots if roots else mesh_objs,
            job['size'], job['squish'], job['height']
        )

        # glTF 뷰어는 절차적 노드를 PBR로 못 넣어 알베도가 하얗게 떨어짐 → EMIT 베이크 후 단순 재질
        bake_sz = int(cfg.get("gltf_bake_size", 1024))
        simplify_materials_for_gltf_export(
            mesh_objs,
            job["disease"],
            cfg["disease_params"],
            bake_size=bake_sz,
            image_basename=job["filename"].replace(".glb", ""),
        )

        out_path = out_dir / job['filename']
        _export_glb(out_path, imported)

        manifest.append(
            {
                "filename": job["filename"],
                "base": job["base_name"],
                "disease": job["disease"],
                "size": job["size"],
                "squish": job["squish"]["label"],
                "height": job["height"],
                "color": job.get("color_label", ""),
                "color_idx": job.get("color_idx"),
            }
        )

    manifest_path = out_dir / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[Tangerine] 완료. manifest → {manifest_path}")


if __name__ == "__main__":
    main()