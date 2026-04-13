# 병해 3D 시각 스펙 (합성용)

2D 실사는 검증용으로 두고, **3D/GLB**는 아래 관찰 형태를 따른다.

| 클래스 | 외형 요지 | 3D 표현 |
|--------|-----------|---------|
| **healthy** | 정상 주황 과피 | 단색 베이스 + 거칠기 |
| **black_spot** | 작은 검은 반점 산재 | 보로노이형 셀로 베이스/반점 혼합 → `black_spot_albedo.png` |
| **canker** | 함몰·궤양, 황색 할로, 갈색 중심 | 큰 셀 + 거리 밴드로 3색 혼합 → `canker_albedo.png` |
| **greening** | 녹·황 모슬, 줄기 쪽 녹색 편향 | 세로 그라데이션 + 노이즈 → `greening_albedo.png` |
| **scab** | 코르크 질 갈색 융기 패치 | 불규칙 패치 + scab 색 → `scab_albedo.png` |

원칙: **Image Texture → Principled Base Color** 위주로 glTF 내보내기 호환.  
베이스 메시는 **Smart UV** (`export_base_mesh.py`).

텍스처 생성: `python scripts/gen_disease_texture_masks.py` → `assets/textures/disease/*.png`
