# Healthy 변종 GLB — 단독 패키지

전체 Tangerine 레포 없이 **건강(healthy) 절차 변종 GLB**만 생성합니다.

## 준비

1. Python 3.10+
2. **Blender** (헤드리스): `apt install blender` (Colab) 또는 [공식 빌드](https://www.blender.org/download/)  
   - 경로를 직접 지정: `export BLENDER_EXE=/usr/bin/blender`
3. 베이스 메시 3개를 `data/Tangerine_3D/` 에 넣기  
   - `tangerine_0.glb`, `tangerine_1.glb`, `tangerine_2.glb`

```bash
pip install -r requirements.txt
```

## 실행 (패키지 루트 = 이 폴더)

```bash
python run_generate_healthy.py --dry-run    # 명령만 확인
python run_generate_healthy.py --no-clean   # 실제 빌드 (다른 병해 폴더 안 지움)
```

처음부터 출력 폴더를 비우고 healthy만 다시 만들려면 `--no-clean` 생략.

**산출:** `data/Tangerine_3D/glb_procedural/healthy/*.glb`

## Google Colab (요약)

```python
# 1) Blender + 의존성
!apt-get update -qq && apt-get install -y -qq blender
!pip install -q pyyaml

# 2) 이 zip을 업로드·압축 해제했다면:
import os
from pathlib import Path
ROOT = Path("/content/Generate_Tangerine_3D_healtht")  # 실제 경로에 맞게
os.chdir(ROOT)

# 3) 베이스 GLB 업로드 → data/Tangerine_3D/
from google.colab import files
uploaded = files.upload()  # tangerine_0/1/2.glb
for name in uploaded:
    if name.endswith(".glb"):
        Path(name).rename(ROOT / "data" / "Tangerine_3D" / name)

# 4) 빌드
!cd {ROOT} && python run_generate_healthy.py --no-clean
```

GPU 런타임은 Blender가 Cycles GPU를 쓰도록 설정된 경우에만 이득이며, 기본은 CPU 베이크일 수 있습니다.

## 폴더 구조

```
Generate_Tangerine_3D_healtht/
  run_generate_healthy.py   # 런처
  configs/variants_batch_healthy.yaml
  src/blender_sim/          # generate_variants 및 재질·베이크 모듈
  scripts/organize_flat_variant_glbs.py
  data/Tangerine_3D/        # 베이스 GLB + (빌드 후) glb_procedural
```
