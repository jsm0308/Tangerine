"""Trigger sources: simulation ticks vs encoder stub (PLC/encoder plug-in later)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TriggerSource(ABC):
    """Logical capture trigger; align with frame index or hardware ticks."""

    @abstractmethod
    def tick_index_for_frame(self, frame_index: int) -> int:
        """Monotonic tick counter for this frame (for logging / queue)."""


class SimulationTickTrigger(TriggerSource):
    """Frame-synchronous ticks: tick grows by tick_stride_frames per frame step."""

    def __init__(self, tick_stride_frames: int) -> None:
        self.tick_stride = max(1, int(tick_stride_frames))

    def tick_index_for_frame(self, frame_index: int) -> int:
        # frame_index is 1-based in file names often; use as step ordinal
        return max(0, int(frame_index)) * self.tick_stride


class EncoderStubTrigger(TriggerSource):
    """Stub encoder: one tick per processed frame (no physical I/O)."""

    def __init__(self) -> None:
        self._count = 0

    def tick_index_for_frame(self, frame_index: int) -> int:
        self._count += 1
        return self._count


class PassthroughTrigger(TriggerSource):
    """No semantic ticks; mirror frame index."""

    def tick_index_for_frame(self, frame_index: int) -> int:
        return int(frame_index)


def make_trigger(mode: str, tick_stride_frames: int) -> TriggerSource:
    m = (mode or "simulation").strip().lower()
    if m == "encoder_stub":
        return EncoderStubTrigger()
    if m == "passthrough":
        return PassthroughTrigger()
    return SimulationTickTrigger(tick_stride_frames)
