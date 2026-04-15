"""Actuation driver plugins: file log, stdout, or no-op."""

from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, TextIO


class ActuationDriver(ABC):
    @abstractmethod
    def emit(self, signal: Dict[str, Any]) -> None:
        """Send one logical actuation decision (hardware-specific subclasses may batch)."""

    def close(self) -> None:
        """Optional cleanup."""


class JsonlDriver(ActuationDriver):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.path, "w", encoding="utf-8")

    def emit(self, signal: Dict[str, Any]) -> None:
        self._fp.write(json.dumps(signal, ensure_ascii=False) + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp and not self._fp.closed:
            self._fp.close()


class PrintDriver(ActuationDriver):
    def __init__(self, stream: TextIO = sys.stdout) -> None:
        self._stream = stream

    def emit(self, signal: Dict[str, Any]) -> None:
        self._stream.write(json.dumps(signal, ensure_ascii=False) + "\n")


class NoopDriver(ActuationDriver):
    def emit(self, signal: Dict[str, Any]) -> None:
        return


def make_driver(kind: str, exp_dir: Path, filename: str) -> ActuationDriver:
    k = (kind or "jsonl").strip().lower()
    if k == "jsonl":
        return JsonlDriver(exp_dir / filename)
    if k == "print":
        return PrintDriver()
    if k == "noop":
        return NoopDriver()
    raise ValueError(f"Unknown postprocess.driver: {kind!r}")
