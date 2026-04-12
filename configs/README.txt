configs/ 안 설정 파일 역할

1) base_mesh.yaml
   - 베이스 과일 GLB만 생성 (단일 메시, 꼭지 없음).
   - 실행: python scripts/build_base_mesh.py
   - 산출: 기본 assets/glb/{tangerine_0,tangerine_1,tangerine_2}.glb

2) variants_batch.yaml
   - 병해·크기·찌그러짐·높이 조합 배치 (405개 등).
   - 선행: 위 베이스 GLB가 있어야 함.
   - 실행: python scripts/generate_variants_build.py

3) default_config.yaml
   - 전역 파이프라인 (main.py 등) + Blender 실행 파일 경로.
