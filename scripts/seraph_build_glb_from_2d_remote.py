#!/usr/bin/env python3
"""
로컬에서 SSH로 Seraph에 접속해 트랙 2 (2D→GLB) 파이프라인을 원격 실행한다.
로컬 CPU로 돌리지 않고 Seraph에서 GPU를 쓰도록 하는 것이 일반적이다.

  python scripts/seraph_build_glb_from_2d_remote.py
  python scripts/seraph_build_glb_from_2d_remote.py --host aurora-seraph --pull

환경 변수 (선택):
  SERAPH_SSH_HOST              SSH config 의 Host 별칭 (기본: aurora-seraph)
  SERAPH_REPO_ROOT             Seraph 상 레포 절대 경로 (기본: /data/minjae051213/Tangerine)
  SERAPH_CUDA_VISIBLE_DEVICES  GPU 인덱스 (기본: 0) — --cuda-device 과 동일 역할
                               none 이면 원격에서 CUDA_VISIBLE_DEVICES 미설정 (SAM 2GPU 병렬용)

원격에 필요한 것:
  conda env(tangerine)·Blender·data/Tangerine_2D·data/Tangerine_3D/tangerine_0~2.glb
  (루트에 둠; rsync/scp로 Seraph와 맞출 것)

선행: ~/.ssh/config, (선택) 클러스터면 Slurm 등은 SERAPH_REMOTE_PRE_CMD 로 모듈/srun 감싸기
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys


def main() -> int:
    p = argparse.ArgumentParser(
        description="SSH → Seraph 에서 build_glb_from_2d (GPU 권장)",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("SERAPH_SSH_HOST", "aurora-seraph"),
        help="SSH config Host",
    )
    p.add_argument(
        "--remote-root",
        default=os.environ.get("SERAPH_REPO_ROOT", "/data/minjae051213/Tangerine"),
        help="Seraph 상 Tangerine 루트",
    )
    p.add_argument(
        "--config",
        default="Generate_Tangerine_3D/from_2d_track/configs/from_2d_batch.yaml",
        help="원격에서 사용할 from_2d_batch.yaml 상대 경로",
    )
    p.add_argument(
        "--pull",
        action="store_true",
        help="원격에서 git pull 후 빌드",
    )
    p.add_argument(
        "--cpu-only",
        action="store_true",
        help="CUDA_VISIBLE_DEVICES 를 설정하지 않음 (Seraph에서 CPU만 쓸 때)",
    )
    p.add_argument(
        "--cuda-device",
        default=os.environ.get("SERAPH_CUDA_VISIBLE_DEVICES", "0"),
        metavar="ID",
        help="원격 CUDA_VISIBLE_DEVICES (기본: 0). none=미설정 — from_2d_batch.yaml 의 sam_parallel_gpus>1 일 때",
    )
    p.add_argument(
        "--remote-pre",
        default=os.environ.get("SERAPH_REMOTE_PRE_CMD", ""),
        metavar="CMD",
        help="cd 레포 전에 실행할 한 줄 (예: Slurm: module load cuda/12.1)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="ssh 명령만 출력",
    )
    p.add_argument(
        "--ssh-v",
        action="store_true",
        help="ssh -v (연결·인증 디버그; 안 붙을 때)",
    )
    args = p.parse_args()

    pull_line = "git pull\n" if args.pull else ""
    root_q = shlex.quote(args.remote_root)
    cfg_q = shlex.quote(args.config)
    pre = (args.remote_pre or "").strip()
    pre_line = (pre + "\n") if pre else ""

    gpu_block = ""
    if not args.cpu_only:
        dev_raw = str(args.cuda_device).strip().lower()
        if dev_raw not in ("none", "no", "-", "off", "all"):
            dev_q = shlex.quote(str(args.cuda_device))
            gpu_block = f'export CUDA_VISIBLE_DEVICES={dev_q}\nexport NVIDIA_VISIBLE_DEVICES=all\n'

    remote_script = f"""set -euo pipefail
echo "[remote] host=$(hostname) time=$(date -Iseconds 2>/dev/null || date)"
{pre_line}cd {root_q}
echo "[remote] cwd=$(pwd)"
{pull_line}if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
fi
if command -v conda >/dev/null 2>&1; then
  conda activate tangerine
fi
export PYTHONUNBUFFERED=1
{gpu_block}python scripts/build_glb_from_2d.py --config {cfg_q}
echo "[remote] build_glb_from_2d done → data/Tangerine_3D/glb_from_2d + decal_cache"
"""

    cmd: list[str] = ["ssh"]
    if args.ssh_v:
        cmd.append("-v")
    # TTY 할당: 원격 echo 가 바로 보이고, 비밀번호 프롬프트도 이 터미널에서 받기 쉬움
    cmd.extend(["-t", args.host, "bash", "-lc", remote_script])
    if args.dry_run:
        print(" ".join(cmd))
        print(remote_script)
        return 0

    print(
        "[seraph] Seraph SSH 접속 중… (여기서 멈추면: 키/비밀번호 입력, 또는 방화벽·Host 키 확인)",
        file=sys.stderr,
    )
    print(" ".join(cmd[:4]), "…", file=sys.stderr)
    if not args.cpu_only:
        msg = (
            f"[seraph] 원격 CUDA_VISIBLE_DEVICES={args.cuda_device}"
            if str(args.cuda_device).strip().lower() not in ("none", "no", "-", "off", "all")
            else "[seraph] 원격 CUDA_VISIBLE_DEVICES 미설정 (SAM 다중 GPU 병렬)"
        )
        print(msg, file=sys.stderr)
    sys.stderr.flush()
    r = subprocess.run(cmd, stdin=sys.stdin)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
