"""JSON 설정 기본값 (런처·Blender 공통).

컨베이어 데모 시나리오(롤러 밀도·스폰 패턴·에피소드 길이·다리 등)는
1) 이 파일의 `default_config()` 를 수정하거나
2) `python Conveyor_Lab/scripts/run_conveyor_demo.py` 가 쓰는 CLI 인자로 덮어쓰거나
3) 실행 후 생성되는 `output_dir/conveyor_demo.json` 을 직접 편집한 뒤
   `blender ... entries/conveyor_entry.py -- path/to/conveyor_demo.json` 으로 재실행
하면 된다.
"""

from __future__ import annotations

from typing import Any, Dict


def default_config() -> Dict[str, Any]:
    return {
        "output_dir": "",
        # 중간 PNG는 `_tmp_frames` 에만 쓰고 끝나면 삭제 (영상만 남김)
        "renders_subdir": "_tmp_frames",
        "delete_intermediate_frames": True,
        "write_metadata": False,
        "metadata_filename": "conveyor_demo_meta.jsonl",
        # 장치
        "belt_length_m": 5.0,
        "belt_width_m": 0.52,
        # 기울기: 월드 Y축 회전(도), +X 방향이 아래로. 0이면 수평. 피벗 기본 X=L/2
        "conveyor_pitch_deg": 15.0,
        "conveyor_pitch_pivot_x_m": None,
        "conveyor_pitch_pivot_z_m": 0.0,
        # 롤러 개수 (클수록 피치가 짧아져 마찰 이송에 유리)
        "roller_count": 108,
        "roller_end_radius_m": 0.026,
        "roller_center_radius_m": 0.0195,
        # 롤러 각속도 (rad/s) — 키네마틱 표면 속도; 이송이 느리면 올릴 것
        "roller_angular_speed_rad_s": 15.0,
        # 롤러–과일 접촉 마찰 (Bullet; 1.0 근처까지)
        "roller_friction": 1.0,
        "roller_restitution": 0.02,
        "roller_collision_shape": "CONVEX_HULL",
        # 과일: sphere = 주황 UV 구(빠름) / glb_citrus = GLB 변종
        "fruit_kind": "sphere",
        "citrus_glb_directory": "outputs/_variant_glb",
        "citrus_spawn_total": 30,
        "preserve_glb_materials": True,
        # 디렉터리가 비어 있거나 없을 때만 사용 (예: 베이스 GLB 3종만)
        "citrus_glb_paths": [
            "data/Tangerine_3D/glb/tangerine0.glb",
            "data/Tangerine_3D/glb/tangerine1.glb",
            "data/Tangerine_3D/glb/tangerine2.glb",
        ],
        "fruit_per_mesh": 10,
        "fruit_target_max_dim_m": 0.09,
        "shuffle_fruit_order": True,
        "fruit_mass_kg": 0.12,
        "fruit_friction": 0.92,
        "fruit_restitution": 0.025,
        # 과일 리지드 댐핑 (너무 튀는 것 완화; None 이면 Blender 기본)
        "fruit_linear_damping": 0.06,
        "fruit_angular_damping": 0.25,
        # 구 모드 호환
        "sphere_count": 30,
        "sphere_uv_segments": 20,
        "sphere_uv_rings": 14,
        "sphere_radius_m": 0.038,
        "sphere_mass_kg": 0.12,
        "sphere_friction": 0.95,
        "sphere_restitution": 0.06,
        "spawn_edge": "min_x",
        "spawn_pad_along_belt_m": 0.06,
        "spawn_y_jitter_m": 0.025,
        "spawn_y_edge_margin_m": 0.03,
        # 기준 높이 × spawn_drop_intensity = 실제 낙하 높이 (기본 25%)
        "spawn_height_above_rollers_m": 0.048,
        "spawn_drop_intensity": 0.25,
        # 스폰 스케줄: batched = 몇 개씩 묶어서 천천히 / uniform = 전 구간 균등
        "spawn_schedule_mode": "batched",
        "spawn_batch_size": 3,
        "spawn_intra_batch_gap_frames": 5,
        "spawn_batch_gap_frames": 48,
        "spawn_start_frame": 28,
        # 데크 지지 다리 (시각용, 정적 메시)
        "conveyor_leg_height_m": 0.74,
        "conveyor_leg_thickness_m": 0.055,
        "conveyor_leg_pairs_along_belt": 3,
        # 측면 레일 (높을수록 튕겨 나감 방지)
        "side_rail_height_m": 0.14,
        "side_rail_thickness_m": 0.022,
        # 벨트 끝: 데크 끊김 + 아래쪽 대형 수집함(과일이 롤러 끝에서 떨어져 수납)
        "end_drop_gap_m": 0.42,
        # None 이면 L - end_drop_gap_m 근처로 자동 (conveyor_mesh)
        "end_drop_deck_cover_end_x_m": None,
        "end_basket_enabled": True,
        "end_basket_depth_m": 0.72,
        "end_basket_inner_width_m": 0.92,
        "end_basket_wall_height_m": 0.42,
        "end_basket_floor_top_z_m": -0.32,
        "end_basket_open_overlap_m": 0.05,
        "side_rail_end_past_deck_m": 0.04,
        # GLB: 경로당 1회 임포트 후 복제 (프레임마다 재임포트 안 함)
        "use_glb_instance_cache": True,
        # 렌더 없이 물리만 돌리고 .blend 저장 — Blender UI에서 재생·탐색
        "skip_render": False,
        "save_blend_path": "",
        # Cycles 전환 시: GPU(OPTIX/CUDA 등) 시도
        "cycles_compute_device": "GPU",
        # 렌더 (EEVEE = 구·프리뷰 빠름 / CYCLES = 품질)
        "cycles_samples": 16,
        "world_bg_strength": 0.4,
        "view_exposure": 0.35,
        # @24fps — 구 스폰 데모는 EEVEE 로 빠르게; 길게는 CLI `--frames`
        "episode_frame_count": 1200,
        "render_engine": "EEVEE",
        "render_fps": 24,
        "render_width": 1280,
        "render_height": 720,
        "seed": 42,
        "conveyor_friction": 0.82,
        "physics_solver_iterations": 28,
        # Bullet 스텝/초 — 높일수록 롤러–과일 접촉이 안정적 (기본: max(120, fps*4))
        "rigidbody_steps_per_second": 240,
        # 카메라: diagonal | line_inspection(qc_line) | top_down(그 외)
        "camera_style": "diagonal",
        "camera_lens_mm": 40.0,
        "camera_diagonal_offset_factors": [0.42, 1.05, 0.92],
        "camera_line_inspection_lens_mm": 35.0,
        "camera_line_inspection_offset_factors": [0.28, 1.28, 0.55],
        "camera_ortho_scale_factor": 1.15,
        "camera_height_m": 7.0,
        # 조명: factory_bay = 천장 스트립+측면(기본) / classic = 예전 강한 에어리어 2+태양
        "lighting_preset": "factory_bay",
        "factory_sun_energy": 0.75,
        "factory_sun_angle_deg": 0.55,
        "factory_ceiling_light_count": 5,
        "factory_ceiling_light_energy": 1600.0,
        "factory_ceiling_height_factor": 1.22,
        "factory_ceiling_light_x_cover": 0.82,
        "factory_side_fill_energy": 850.0,
        "factory_spot_rig_enabled": False,
        "factory_spot_energy": 420.0,
        "factory_spot_size": 0.35,
        # 최종 영상 파일명 (프로젝트 루트 output_dir 기준)
        "output_video_name": "conveyor_run.mp4",
    }


def merge_config(overrides: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg = default_config()
    if overrides:
        cfg.update(overrides)
    return cfg
