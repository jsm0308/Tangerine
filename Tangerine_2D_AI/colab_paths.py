"""Colab 등에서 zip 이중 폴더 여부와 관계없이 데이터·코드 경로를 찾기 위한 헬퍼."""

from __future__ import annotations

from pathlib import Path

# 데이터셋에 흔히 쓰는 클래스 폴더명 (일부만 있어도 매칭)
_CLASS_DIR_MARKERS = frozenset(
    {"healthy", "Black spot", "Canker", "Greening", "Scab"}
)


def resolve_project_root(search: Path = Path("/content")) -> Path:
    """`Tangerine_2D_AI/config.py`가 있는 디렉터리 (얕은 경로 우선)."""
    hits = list(search.glob("**/Tangerine_2D_AI/config.py"))
    if not hits:
        raise FileNotFoundError(
            "Tangerine_2D_AI/config.py 를 찾을 수 없습니다. "
            "Tangerine_2D_AI.zip 을 /content 에 두고 압축을 풀었는지 확인하세요."
        )
    return min((p.parent for p in hits), key=lambda p: len(p.parts))


def resolve_data_root(search: Path = Path("/content")) -> Path:
    """
    이름이 `Tangerine_2D`인 폴더 중, 클래스 하위 폴더가 있는 것을 선택.
    `Tangerine_2D/Tangerine_2D/...` 처럼 중첩돼 있어도 glob으로 하나를 고른다.
    """
    candidates: list[Path] = []
    for p in search.glob("**/Tangerine_2D"):
        if not p.is_dir():
            continue
        sub_names = {d.name for d in p.iterdir() if d.is_dir()}
        if not sub_names:
            continue
        if sub_names & _CLASS_DIR_MARKERS or len(sub_names) >= 3:
            candidates.append(p)
    if not candidates:
        raise FileNotFoundError(
            "Tangerine_2D 데이터 폴더(클래스 하위 폴더 포함)를 찾을 수 없습니다."
        )
    return min(candidates, key=lambda p: len(p.parts))
