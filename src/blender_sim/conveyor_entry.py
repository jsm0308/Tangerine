"""

Blender에서만 실행:



  blender --background --factory-startup --python src/blender_sim/conveyor_entry.py -- path/to/conveyor_demo.json



`scripts/run_conveyor_demo.py` 가 JSON을 생성해 Blender를 호출합니다.

JSON 키 예: ``skip_render`` / ``save_blend_path`` — PNG 없이 물리만 돌린 뒤 ``.blend`` 저장 시
Blender 앱에서 해당 파일을 열고 타임라인 재생으로 3D 확인(줌·회전) 가능.

"""



from __future__ import annotations



import json

import sys

from pathlib import Path



if "--" not in sys.argv:

    print(

        "Usage: blender --background --factory-startup --python src/blender_sim/conveyor_entry.py -- conveyor_demo.json"

    )

    sys.exit(1)



cfg_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()



PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(0, str(PROJECT_ROOT))



from src.blender_sim.conveyor_demo.run import run_demo  # noqa: E402



with open(cfg_path, "r", encoding="utf-8") as f:

    cfg = json.load(f)



run_demo(cfg)


