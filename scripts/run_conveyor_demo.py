#!/usr/bin/env python3

"""

프로시저 컨베이어(5m 롤러) + GLB 스폰 또는 구 물리 데모.

- 기본: `outputs/_variant_glb/` 에서 GLB 30개(병해 재질 유지), 폴더가 없으면 `assets/glb/` 3종×10

  python scripts/run_conveyor_demo.py

  python scripts/run_conveyor_demo.py --frames 300 --cycles 14

  python scripts/run_conveyor_demo.py --roller-speed 5.5

  python scripts/run_conveyor_demo.py --preview-blend --no-video   # .blend 만

  python scripts/run_conveyor_demo.py --also-blend                 # MP4 + conveyor_scene.blend

"""



from __future__ import annotations



import argparse

import json

import os

import shutil

import subprocess

import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

ENTRY = ROOT / "src" / "blender_sim" / "conveyor_entry.py"



if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from src.blender_sim.conveyor_demo.defaults import merge_config  # noqa: E402





def _find_blender_executable() -> str | None:

    for key in ("BLENDER_EXECUTABLE", "BLENDER"):

        v = (os.environ.get(key) or "").strip().strip('"')

        if v and Path(v).is_file():

            return v

    for name in ("blender", "blender.exe"):

        w = shutil.which(name)

        if w:

            return w

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))

    bf = program_files / "Blender Foundation"

    if bf.is_dir():

        subs = sorted(

            (p for p in bf.iterdir() if p.is_dir()),

            key=lambda p: p.name,

            reverse=True,

        )

        for sub in subs:

            exe = sub / "blender.exe"

            if exe.is_file():

                return str(exe)

    return None


def _stitch_pngs_to_mp4_opencv(renders_dir: Path, out_mp4: Path, fps: float) -> bool:
    """ffmpeg 없을 때 OpenCV로 MP4 생성 (프로젝트에 opencv-python 있을 때)."""
    try:
        import glob

        import cv2
    except ImportError:
        return False
    imgs = sorted(glob.glob(str(renders_dir / "frame_*.png")))
    if not imgs:
        return False
    first = cv2.imread(imgs[0])
    if first is None:
        return False
    h, w = first.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(out_mp4), fourcc, float(fps), (w, h))
    for p in imgs:
        im = cv2.imread(p)
        if im is not None:
            vw.write(im)
    vw.release()
    return out_mp4.is_file()


def main() -> int:

    p = argparse.ArgumentParser(description="Procedural roller conveyor + fruit spheres (Blender)")

    p.add_argument(

        "--out",

        type=Path,

        default=ROOT / "outputs" / "conveyor_demo",

        help="Output directory",

    )

    p.add_argument("--blender", type=str, default="", help="Blender executable path")

    p.add_argument("--frames", type=int, default=None, help="Timeline length (frames)")

    p.add_argument("--spheres", type=int, default=None, help="Total fruit count")

    p.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Cycles samples per frame (lower = faster, less RAM; default from defaults.py)",
    )

    p.add_argument(
        "--roller-speed",
        type=float,
        default=None,
        metavar="RAD_S",
        help="Roller angular speed in rad/s (maps to roller_angular_speed_rad_s)",
    )

    p.add_argument("--no-video", action="store_true", help="Skip ffmpeg MP4")

    p.add_argument(
        "--preview-blend",
        action="store_true",
        help="Skip PNG render; run physics only and save conveyor_scene.blend for Blender UI",
    )

    p.add_argument(
        "--cpu-cycles",
        action="store_true",
        help="Force Cycles on CPU (ignore defaults GPU)",
    )

    p.add_argument(
        "--also-blend",
        action="store_true",
        help="After full PNG+MP4 render, also save conveyor_scene.blend (skip_render stays off)",
    )

    args = p.parse_args()



    exe = (args.blender or "").strip() or _find_blender_executable()

    if not exe:

        print(

            "Blender not found. Set PATH, BLENDER_EXECUTABLE, or --blender.",

            file=sys.stderr,

        )

        return 3



    args.out.mkdir(parents=True, exist_ok=True)

    cfg_path = args.out / "conveyor_demo.json"



    overrides: dict = {

        "output_dir": str(args.out.resolve()),

    }

    if args.frames is not None:

        overrides["episode_frame_count"] = args.frames

    if args.spheres is not None:

        overrides["sphere_count"] = args.spheres

    if args.cycles is not None:

        overrides["cycles_samples"] = args.cycles

    if args.roller_speed is not None:

        overrides["roller_angular_speed_rad_s"] = args.roller_speed

    if args.preview_blend and args.also_blend:

        print("--preview-blend 와 --also-blend 는 함께 쓰지 마세요.", file=sys.stderr)

        return 2

    if args.preview_blend:

        overrides["skip_render"] = True

        overrides["save_blend_path"] = "conveyor_scene.blend"

    elif args.also_blend:

        overrides["save_blend_path"] = "conveyor_scene.blend"

    if args.cpu_cycles:

        overrides["cycles_compute_device"] = "CPU"



    cfg = merge_config(overrides)

    with open(cfg_path, "w", encoding="utf-8") as f:

        json.dump(cfg, f, indent=2, ensure_ascii=False)



    cmd = [exe, "--background", "--factory-startup", "--python", str(ENTRY), "--", str(cfg_path)]

    print("Running:", " ".join(cmd))

    subprocess.run(cmd, check=True)

    if cfg.get("skip_render"):

        blend_name = cfg.get("save_blend_path") or "conveyor_scene.blend"

        print(f"Preview .blend (Blender에서 파일 열기 → 타임라인 재생): {args.out / blend_name}")

        return 0

    renders_dir = args.out / cfg.get("renders_subdir", "_tmp_frames")
    fps = float(cfg["render_fps"])
    vid_name = cfg.get("output_video_name", "conveyor_run.mp4")
    mp4_out = args.out / vid_name

    if not args.no_video:
        pattern = renders_dir / "frame_%04d.png"
        ff = shutil.which("ffmpeg")
        if ff:
            fc = [
                ff,
                "-y",
                "-framerate",
                str(int(fps)),
                "-i",
                str(pattern),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(mp4_out),
            ]
            print("Encoding:", " ".join(fc))
            subprocess.run(fc, check=True)
            print(f"Video: {mp4_out}")
        elif _stitch_pngs_to_mp4_opencv(renders_dir, mp4_out, fps):
            print(f"ffmpeg missing; wrote MP4 via OpenCV: {mp4_out}")
        else:
            print(
                "ffmpeg not in PATH and OpenCV stitch failed; see intermediate PNGs in",
                renders_dir,
            )

        if cfg.get("save_blend_path") and not cfg.get("skip_render"):
            print(f"Blender scene also saved: {args.out / cfg.get('save_blend_path')}")

        if cfg.get("delete_intermediate_frames", True) and renders_dir.is_dir():
            shutil.rmtree(renders_dir, ignore_errors=True)
            print(f"Removed intermediate frames under {renders_dir.name}/")
    else:
        print(f"Intermediate PNGs (no video): {renders_dir}")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


