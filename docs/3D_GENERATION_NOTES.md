# 3D 생성 시도 메모

프로토타입이라 **만족할 때까지 반복**하고, 여기엔 **한 일 / 생긴 문제**만 짧게 남긴다.

---

## 1차

- **한 일:** 베이스 GLB → 절차 병해 셰이더 → glTF용 **알베도·거칠기·노멀 베이크** 후 `data/Tangerine_3D/glb_procedural/` 에 저장. 설정은 `variants_batch.yaml`, 실행은 `python scripts/generate_variants_build.py`.
- **문제:** 실물 대비 **합성 느낌**, 베이크로 절차 정보가 **텍스처에 압축**됨. 일부 병해는 Voronoi 때문에 **격자 느낌**.

---

## 2차

- **한 일:** 베이크 샘플·YAML 튜닝, Blender 5.1 `TexImage` colorspace 는 이미지 데이터블록으로 처리. 출력 폴더 정리·`--clean` 빌드 UX. 병해·black spot 등 파라미터 조정.
- **문제:** 위 한계는 남음. 품질은 계속 **YAML·셰이더·베이크**로 조정하는 중.

---

## 다음에 쓸 때

```text
### N차
- 한 일:
- 문제 / 다음:
```

---

## 건강 귤 GLB (243개)

**렌더 PNG는 레포에 고정해 두지 않음** — GLB만 두고 뷰어·Blender로 본다.

**243 = 3 메시 × 3 전체 크기 × 3 색 × 3 높이(0.95~1.05) × 3 형태(울퉁불퉁 근사)**  
형태는 메시 굴곡이 아니라 **XY vs Z 스케일 비**만 살짝 바꾼 것(타원체에 가깝게). 설정은 `Generate_Tangerine_3D/procedural_track/configs/variants_batch_healthy.yaml`.

`mesh_bases/tangerine0~2.glb` 가 있을 때:

```bash
python scripts/generate_variants_build.py --config Generate_Tangerine_3D/procedural_track/configs/variants_batch_healthy.yaml --no-clean
```

`--no-clean` 으로 **다른 병해 폴더·기존 GLB는 삭제하지 않음.** `merge_existing_manifest` 로 `manifest.json` 의 **healthy 항목만** 새 목록으로 갈아끼운다.

전체(병해 포함)를 한 번에 다시 만들 때는 기존 `variants_batch.yaml` 로 돌리면 된다.
