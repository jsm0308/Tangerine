"""Phase 1: triggers and belt slot indexing."""

from .slots import belt_slot_index, bbox_center_xy, camera_offset_slots, slot_for_box
from .triggers import (
    EncoderStubTrigger,
    PassthroughTrigger,
    SimulationTickTrigger,
    TriggerSource,
    make_trigger,
)

__all__ = [
    "belt_slot_index",
    "bbox_center_xy",
    "camera_offset_slots",
    "slot_for_box",
    "EncoderStubTrigger",
    "PassthroughTrigger",
    "SimulationTickTrigger",
    "TriggerSource",
    "make_trigger",
]
