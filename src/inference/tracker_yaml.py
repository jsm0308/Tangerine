"""Resolve Ultralytics tracker config from profile names or custom paths."""

from __future__ import annotations


def resolve_tracker_yaml(tracker: str, tracker_profile: str) -> str:
    """Map tracker_profile botsort/bytetrack to built-in yaml; else use tracker."""
    p = (tracker_profile or "").strip().lower()
    if p == "botsort":
        return "botsort.yaml"
    if p == "bytetrack":
        return "bytetrack.yaml"
    return (tracker or "").strip() or "bytetrack.yaml"
