#!/usr/bin/env python3
"""
로컬(Windows 등)에서 SSH로 Seraph에 접속해 변종 GLB 파이프라인을 원격 실행한다.

  python scripts/seraph_build_variants_remote.py
  python scripts/seraph_build_variants_remote.py --host aurora-seraph --pull

환경 변수 (선택):
  SERAPH_SSH_HOST    SSH config 의 Host 별칭 (기본: aurora-seraph)
  SERAPH_REPO_ROOT     Seraph 상 레포 절대 경로 (기본: /data/minjae051213/Tangerine)

선행: ~/.ssh/config 에 Host 가 설정되어 있고, Seraph 에 레포·conda env tangerine·Blender 가 준비되어 있어야 한다.
      docs/SERAPH_REMOTE_GUIDE.md 참고.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="SSH → Seraph 에서 variant GLB 빌드")
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
        "--pull",
        action="store_true",
        help="원격에서 git pull 후 빌드",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="ssh 명령만 출력",
    )
    args = p.parse_args()

    pull_line = "git pull\n" if args.pull else ""
    root_q = shlex.quote(args.remote_root)

    remote_script = f"""set -euo pipefail
cd {root_q}
{pull_line}if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
fi
if command -v conda >/dev/null 2>&1; then
  conda activate tangerine
fi
export PYTHONUNBUFFERED=1
python scripts/gen_disease_texture_masks.py
python scripts/build_base_mesh.py
python scripts/generate_variants_build.py
echo "[remote] done"
"""

    cmd = ["ssh", args.host, "bash", "-lc", remote_script]
    if args.dry_run:
        print(" ".join(cmd[:3]))
        print(remote_script)
        return 0

    print(" ".join(cmd[:3]), "(remote bash -lc …)", file=sys.stderr)
    r = subprocess.run(cmd)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
