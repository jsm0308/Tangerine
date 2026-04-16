data/Tangerine_3D — 최종 3D 산출물만 (루트 기준 상대 경로)

  (루트)            — 베이스 GLB 3개: tangerine_0.glb ~ tangerine_2.glb (from_2d·절차 변종 YAML 이 동일 경로 참조; mesh_bases 복제 불필요)

  glb_procedural/   — 트랙 1: 절차 셰이더·YAML·베이크로 만든 변종 GLB (generate_variants_build.py)
                      각 파일은 healthy / Black spot / Canker / Greening / Scab 하위 폴더에 둔다.
                      루트에 *.glb 가 남았으면: python scripts/organize_flat_variant_glbs.py
  glb_from_2d/      — 트랙 2: 2D 텍스처·이미지를 메쉬에 씌운 뒤 내볂인 GLB

빌드용 설정·베이스 메시·참고 텍스처는 Generate_Tangerine_3D/ 를 본다.

품질 자동 루프(렌더 캡처 → 수치 QC):
  python scripts/variant_qc_pipeline.py
기존 GLB만 캡처·QC:
  python scripts/qc_preview_only.py
  (미리보기 PNG: data/Tangerine_3D/glb_procedural/_qc_previews/ )
