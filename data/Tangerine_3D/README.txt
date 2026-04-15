귤 3D 파이프라인 전용 루트 (프로젝트 루트 기준 상대 경로).

  glb/              — 베이스 tangerine0–2.glb, 컨베이어 벨트 GLB, conveyor_glb_export.json 등
  textures/disease/ — 병해 참고용 알베도 PNG (gen_disease_texture_masks.py)
  configs/          — variants_batch.yaml, base_mesh.yaml
  (레포 루트) outputs/_variant_glb/ — generate_variants_build.py 산출 GLB·manifest.json

스크립트 기본값은 이 폴더를 가리킵니다. 코드는 레포 루트의 src/, scripts/ 에 그대로 있습니다.

품질 자동 루프(렌더 캡처 → 수치 QC → 실패 시 YAML disease_params 보정 후 재빌드):
  python scripts/variant_qc_pipeline.py
기존 GLB만 캡처·QC(재빌드 없음):
  python scripts/qc_preview_only.py
  (미리보기 PNG: outputs/_variant_glb/_qc_previews/ )
