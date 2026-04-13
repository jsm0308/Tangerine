# 롤러 컨베이어 데모 — 물리 조정·GLB 캐시·실행

진입: `python scripts/run_conveyor_demo.py` → Blender 서브프로세스 → `src/blender_sim/conveyor_demo/run.py`  
설정 기본값: `src/blender_sim/conveyor_demo/defaults.py` (런처가 `output_dir/conveyor_demo.json` 으로 덮어쓸 수 있음).

---

## 1. 귤이 벨트를 따라 잘 이동하도록 한 조정 (요약)

| 설정 | 역할 |
|------|------|
| **촘촘한 롤러** `roller_count` (기본 108) | 롤러 피치 짧게 → 과일–롤러 접촉 많음 |
| **롤러 각속도** `roller_angular_speed_rad_s` (기본 9.0 rad/s) | 키네마틱 롤러 회전 → 표면이 +X 방향으로 밀어 줌 |
| **롤러/과일 마찰** `roller_friction`, `fruit_friction` | 접선 방향 힘 전달 |
| **낙하 약하게** `spawn_height_above_rollers_m` × `spawn_drop_intensity` (기본 0.25) | “던져지는” 느낌 완화 |
| **튐 완화** `fruit_restitution`, 댐핑 | 데크·레일·바구니와 함께 튕김 감소 |
| **Bullet** `rigidbody_steps_per_second`, `physics_solver_iterations` | 접촉 안정성 |
| **높은 사이드 레일** `side_rail_height_m` | 옆으로 튕겨 나감 완화 |
| **끝 바구니** `end_basket_*` | 벨트 끝에서 수집 |

세부 수식·축 방향은 `roller_motion.py` 주석 참고.

---

## 2. GLB를 매 프레임 다시 만들지 않음 (인스턴스 캐시)

- `use_glb_instance_cache` 가 **true**(기본)이면, **같은 경로의 GLB는 한 번만** glTF 임포트·스케일·머티리얼 처리하고, 스폰마다 **메시 복제**로 인스턴스만 만든다 (`objects/fruit.py`: `build_glb_template` / `duplicate_fruit_from_template`).
- **반복 실행 시에도** 디스크의 GLB 파일은 그대로 두고, Blender 프로세스 안에서만 캐시가 유효하다 (실행 종료 시 메모리 해제).

---

## 3. 입력 GLB가 어디를 보는지

`defaults.py` 기준:

- 우선 **`citrus_glb_directory`** (예: `outputs/_variant_glb`)에서 총 `citrus_spawn_total` 개를 고른다.  
- 디렉터리가 비어 있으면 **`citrus_glb_paths`** (예: `assets/glb/*.glb`) 목록을 사용한다.  
- Seraph에서는 위 경로들이 **서버의 Tangerine 루트 기준**으로 존재해야 한다 (`git pull` + 필요 시 GLB 빌드 스크립트로 생성).

---

## 4. 한 번에 하나의 무거운 작업

GPU·장시간 렌더는 **동시에 여러 개** 돌리면 느려지거나 OOM 날 수 있음. **컨베이어 1작업 + 다른 Blender 1작업** 동시 실행은 피하거나, 프레임·샘플을 줄일 것.

---

## 5. Seraph에서 생성·실행 (요약)

전제: SSH 접속, Conda `tangerine`, 레포 `cd /data/minjae051213/Tangerine`, `pip install -r requirements.txt` 완료, `blender` 사용 가능.

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate tangerine
cd /data/minjae051213/Tangerine
git pull   # 최신 코드

# (필요 시) 변종 GLB 먼저 — outputs/_variant_glb/ 채움
# python scripts/generate_variants_build.py

# 컨베이어: 짧은 테스트 예시 (서버 부담에 맞게 frames/cycles 조절)
python scripts/run_conveyor_demo.py --out outputs/conveyor_demo --frames 200 --cycles 8 --also-blend
```

Blender가 PATH에 없으면 `--blender /절대/경로/blender` 추가.  
산출물: `outputs/conveyor_demo/conveyor_run.mp4`, 옵션 `conveyor_scene.blend`, 중간 PNG는 설정에 따라 삭제.

자세한 SSH·Conda: [SERAPH_REMOTE_GUIDE.md](SERAPH_REMOTE_GUIDE.md)  
로컬 vs 서버 파일: [SERAPH_AND_LOCAL.md](SERAPH_AND_LOCAL.md)
