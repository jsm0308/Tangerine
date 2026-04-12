# src/blender_sim/generate_variants.py
"""
헤드리스 Blender 배치 변종 생성기.

실행:
  blender --background --python src/blender_sim/generate_variants.py \\
          -- --config configs/variants_batch.yaml

  # 실제 내보내기 없이 목록만 확인:
  blender --background --python src/blender_sim/generate_variants.py \\
          -- --config configs/variants_batch.yaml --dry-run

출력:
  <output_dir>/<base>__<disease>__s<N>__q<N>__h<N>.glb   (N = 1-based index)
  <output_dir>/manifest.json
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

from disease_materials import apply_disease_material

# 설정은 (1) --job-json (권장: 래퍼가 YAML→JSON) 또는 (2) --config YAML — 후자는 Blender 내 PyYAML 필요.

# ─── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--job-json", default=None, help="래퍼가 만든 해석된 설정 JSON (PyYAML 불필요)")
    p.add_argument("--config", default="configs/variants_batch.yaml")
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

def _gen_values(spec: dict, rng: random.Random) -> list:
    if spec.get('auto_generate', True):
        lo, hi, n = spec['min'], spec['max'], spec['count']
        return [round(rng.uniform(lo, hi), 4) for _ in range(n)]
    return list(spec['values'])

def build_jobs(cfg: dict) -> list:
    rng         = random.Random(cfg.get('random_seed', 42))
    size_vals   = _gen_values(cfg['size_variants'],   rng)
    height_vals = _gen_values(cfg['height_variants'], rng)
    squish_list = cfg['squish_variants']
    diseases    = list(cfg['disease_params'].keys())
    sources     = cfg['glb_sources']

    jobs = []
    for src in sources:
        for dis in diseases:
            for si, sv in enumerate(size_vals, 1):
                for qi, sq in enumerate(squish_list, 1):
                    for hi, hv in enumerate(height_vals, 1):
                        fname = f"{src['name']}__{dis}__s{si}__q{qi}__h{hi}.glb"
                        jobs.append({
                            'base_name': src['name'],
                            'glb_path':  src['path'],
                            'disease':   dis,
                            'size':      sv,
                            'squish':    sq,   # dict: {label, scale_xy, scale_z}
                            'height':    hv,
                            'filename':  fname,
                        })
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

        # 병해 재질 적용 (모든 메시)
        for mobj in mesh_objs:
            apply_disease_material(mobj, job['disease'], cfg['disease_params'])

        # 트랜스폼 적용 (루트 없으면 메시 직접 사용)
        _apply_transform(
            roots if roots else mesh_objs,
            job['size'], job['squish'], job['height']
        )

        out_path = out_dir / job['filename']
        _export_glb(out_path, imported)

        manifest.append({
            'filename': job['filename'],
            'base':     job['base_name'],
            'disease':  job['disease'],
            'size':     job['size'],
            'squish':   job['squish']['label'],
            'height':   job['height'],
        })

    manifest_path = out_dir / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[Tangerine] 완료. manifest → {manifest_path}")


if __name__ == "__main__":
    main()