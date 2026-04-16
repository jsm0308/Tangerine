# 롤러 컨베이어 데모

`main.py` **밖**에서 돌리는 Blender 작업이다. 프로시저로 롤러·데크·레일·수집함을 만들고, 물리(리지드 바디) 후 프레임을 렌더해 **MP4**로 합친다.

| 역할 | 경로 |
|------|------|
| 호스트 런처 | `Conveyor_Lab/scripts/run_conveyor_demo.py` |
| Blender 진입 | `src/blender_sim/entries/conveyor_entry.py` → `conveyor/run.py` |
| 기본값 | `src/blender_sim/conveyor/defaults.py` |
| 실행 시 생성 | `{출력폴더}/conveyor_demo.json` (병합 설정) |

---

## 1. 로컬 실행

```bash
pip install -r requirements.txt   # imageio-ffmpeg 권장(MP4)
python Conveyor_Lab/scripts/run_conveyor_demo.py --out Conveyor_Lab/outputs/conveyor_demo
```

짧게 테스트만:

```bash
python Conveyor_Lab/scripts/run_conveyor_demo.py --out Conveyor_Lab/outputs/conveyor_demo --frames 240
```

인자 없이 실행하면 기본 출력은 `Conveyor_Lab/outputs/conveyor_demo` 이다.

| CLI | 설정 키 / 설명 |
|-----|----------------|
| `--frames N` | `episode_frame_count` |
| `--spheres N` | `sphere_count` |
| `--roller-speed` | `roller_angular_speed_rad_s` (rad/s) |
| `--pitch-deg` | `conveyor_pitch_deg` (월드 Y축, +X 내리막) |
| `--no-video` | PNG만 / 인코딩 생략 |
| `--preview-blend` | 렌더 생략, `.blend` 저장 |
| `--also-blend` | MP4 후 `.blend`도 저장 |
| `--blender` | Blender 실행 파일 경로 |

Blender가 PATH에 없으면 `--blender` 또는 환경 변수 `BLENDER_EXECUTABLE`.

### Blender에서 장면 확인

가능하다. 씬은 Blender에서 그대로 열고 타임라인 재생·뷰포트·재질을 볼 수 있다.

| 방법 | 명령 / 결과 |
|------|-------------|
| 빠르게(렌더 생략) | `python Conveyor_Lab/scripts/run_conveyor_demo.py --preview-blend --no-video --out …` → `conveyor_scene.blend` 만 생성. Blender에서 파일 열기 → 스페이스로 재생. |
| 영상까지 만든 뒤 | `--also-blend` 를 추가하면 MP4 렌더 후 같은 폴더에 `.blend` 도 저장. |
| 수동 | 생성된 `conveyor_demo.json` 을 고친 뒤 `blender --background --python src/blender_sim/entries/conveyor_entry.py -- path/to/conveyor_demo.json` (헤드리스). UI로 보려면 `--background` 없이 실행하는 방식은 진입 스크립트 설계상 권장하지 않음 — 위 `.blend` 저장 경로가 가장 단순하다. |

### 카메라·공장 조명 (설정)

`src/blender_sim/conveyor/camera.py` 에서 배치한다. `defaults.py` 또는 `conveyor_demo.json` 으로 조정한다.

| 키 | 설명 |
|----|------|
| `camera_style` | `diagonal`(기본 대각선) / `line_inspection`(라인 QC에 가까운 측면·낮은 시점) / 그 외 → 탑다운 정사영 |
| `camera_lens_mm` | 대각선 투시 초점거리(mm) |
| `camera_diagonal_offset_factors` | `[fx, fy, fz]` 벨트 `span` 배율로 카메라 위치 (대각선 모드) |
| `camera_line_inspection_lens_mm` / `camera_line_inspection_offset_factors` | 라인 검사 뷰용 초점·오프셋 |
| `lighting_preset` | `factory_bay`(기본: 천장 스트립 + 측면 필 + 약한 태양) / `classic`(예전 강한 에어리어 2 + 태양) |
| `factory_ceiling_light_count` / `factory_ceiling_light_energy` / `factory_ceiling_height_factor` | 천장 조명 개수·세기·높이 |
| `factory_spot_rig_enabled` | `true` 이면 벨트 위쪽에 보조 스팟(비전 조명 느낌) 추가 |

`view_exposure`, `world_bg_strength` 로 전체 노출·배경도 맞출 수 있다.

---

## 2. 산출물 (`--out` 기준)

| 산출 | 설명 |
|------|------|
| `conveyor_run.mp4` | ffmpeg 또는 번들 `imageio-ffmpeg`로 합성 성공 시 |
| `_tmp_frames/frame_*.png` | 중간 PNG; 성공 시 `delete_intermediate_frames`에 따라 삭제 |
| `conveyor_demo.json` | 이번 실행에 사용한 병합 설정 |
| `conveyor_scene.blend` | `--also-blend` / `--preview-blend` 일 때 |

---

## 3. 모듈·설정 (한 곳에서만)

| 주제 | 키 / 파일 |
|------|-----------|
| **기울기** | `conveyor_pitch_deg`(기본 15), `conveyor_pitch_pivot_x_m`(None이면 벨트 길이의 ½), `conveyor_pitch_pivot_z_m` — 구현 `conveyor_pitch.py` |
| **과일** | 기본 `fruit_kind`: `sphere`, 주황 구 `sphere_count`개. GLB 쓰려면 `glb_citrus` + `citrus_glb_directory` 또는 `citrus_glb_paths` |
| **렌더** | 기본 `render_engine`: EEVEE; Cycles 쓰면 `cycles_samples` 등. Blender 5.x는 사용 가능한 EEVEE enum 자동 선택(`run.py`) |
| **롤러 물리** | `roller_angular_speed_rad_s`, `roller_friction`, `roller_count`, `roller_end_radius_m` — 키네마틱·마찰은 `roller_motion.py` |
| **끝·레일** | `end_drop_gap_m`, `end_basket_*`, `side_rail_end_past_deck_m` — 메시 `conveyor_mesh.py` |

**정적 GLB만** 필요할 때 (물리·과일·렌더 없음):

```bash
python Conveyor_Lab/scripts/export_conveyor_glb.py --out Conveyor_Lab/outputs/glb/conveyor_belt.glb
```

게임/에셋 파이프라인용으로 `Generate_Tangerine_3D/procedural_track/mesh_bases/` 에 두려면 `--out Generate_Tangerine_3D/procedural_track/mesh_bases/conveyor_belt.glb` 로 지정하면 된다.

`--overrides x.json`으로 위와 **같은 키**로 덮어쓴다. 산출: `.glb` + `conveyor_glb_export.json`.

---

## 4. glb_citrus일 때만: GLB 경로·캐시

- 경로: `citrus_glb_directory`에 `*.glb`가 있으면 우선 사용, 없으면 `citrus_glb_paths`.
- `use_glb_instance_cache`: 동일 GLB는 한 번 임포트 후 복제 (`objects/fruit.py`).

---

## 5. 물리 튜닝 참고표

| 설정 | 역할 |
|------|------|
| `roller_angular_speed_rad_s` | 롤러 각속도 → 표면이 +X로 밀어 줌 |
| `roller_friction`, `sphere_friction` / `fruit_friction` | 롤러–과일 접촉 |
| `roller_count` | 롤러 촘촘함(피치) |
| `spawn_height_above_rollers_m`, `spawn_drop_intensity` | 스폰 높이·“던짐” 느낌 |
| `rigidbody_steps_per_second`, `physics_solver_iterations` | Bullet 안정성 |
| `conveyor_friction` | 데크 등 **정적** 부품과의 마찰 |

축·수식은 `roller_motion.py`, `spawn.py` 주석 참고.

---

## 6. 원격(Seraph)·Git

레포 맞추기, SSH, Conda, 결과 파일 가져오기는 **[SERAPH.md](../../docs/SERAPH.md)** 한 곳에 정리했다. 컨베이어 예시 명령은 그 문서 8절.

---

## 7. 부하

긴 `episode_frame_count`·고해상도·Cycles는 시간·VRAM을 많이 쓴다. 서버에서 동시에 무거운 Blender 여러 개는 피한다.
