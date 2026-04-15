"""
롤러 컨베이어 운동: 키네마틱 패시브 리지드바디 + 오일러 회전 키프레임.

`conveyor_mesh` 의 아워글래스 롤러는 로컬 **Y** 가 축(벨트 폭 방향)이고,
단면은 **XZ** 평면이다. 따라서 벨트 진행(+X) 방향으로 윗면이 밀려 나가려면
**rotation_euler[1] (Y축)** 을 시간에 따라 증가시킨다 (오메가 > 0).

Blender Bullet은 키네마틱 애니메이션된 패시브와 액티브 사이에 마찰을 적용하므로,
롤러 표면의 접선 속도가 과일에 전달되어 컨베이어 끝까지 밀어 줄 수 있다.
"""

from __future__ import annotations

from typing import Any, Dict, List

import bpy

from src.blender_sim.conveyor import physics as phys

# 롤러 메시 축이 로컬 Y 이므로 벨트(+X) 이송용 회전은 오일러 Y
ROLLER_ROTATION_EULER_INDEX = 1


def setup_kinematic_rollers(
    scene: bpy.types.Scene,
    rollers: List[bpy.types.Object],
    *,
    episode_frames: int,
    fps: int,
    angular_speed_rad_s: float,
    friction: float,
    restitution: float = 0.02,
    collision_shape: str = "CONVEX_HULL",
) -> None:
    """롤러를 패시브·키네마틱으로 두고, 1프레임~끝프레임까지 일정 각속도로 회전 키프레임."""
    for r in rollers:
        phys.add_passive_rb(
            r,
            friction=friction,
            collision_shape=collision_shape,
            kinematic=True,
            restitution=restitution,
        )

    total_s = max(1e-6, (episode_frames - 1) / max(1, fps))
    end_angle_delta = angular_speed_rad_s * total_s

    scene.frame_set(1)
    for r in rollers:
        r.keyframe_insert(data_path="location", frame=1)
        r.keyframe_insert(data_path="rotation_euler", frame=1)

    scene.frame_set(episode_frames)
    for r in rollers:
        re = list(r.rotation_euler)
        re[ROLLER_ROTATION_EULER_INDEX] += end_angle_delta
        r.rotation_euler = re
        r.keyframe_insert(data_path="location", frame=episode_frames)
        r.keyframe_insert(data_path="rotation_euler", frame=episode_frames)


def setup_rollers_from_config(
    scene: bpy.types.Scene,
    rollers: List[bpy.types.Object],
    cfg: Dict[str, Any],
) -> None:
    """설정 dict에서 롤러 마찰·각속도·충돌 형상을 읽어 `setup_kinematic_rollers` 호출."""
    episode = int(cfg["episode_frame_count"])
    fps = int(cfg["render_fps"])
    omega = float(cfg["roller_angular_speed_rad_s"])
    friction = float(cfg.get("roller_friction", cfg.get("conveyor_friction", 0.82)))
    restitution = float(cfg.get("roller_restitution", 0.02))
    collision_shape = str(cfg.get("roller_collision_shape", "CONVEX_HULL"))
    setup_kinematic_rollers(
        scene,
        rollers,
        episode_frames=episode,
        fps=fps,
        angular_speed_rad_s=omega,
        friction=friction,
        restitution=restitution,
        collision_shape=collision_shape,
    )
