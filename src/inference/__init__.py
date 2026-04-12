"""
Inference: YOLO detection + tracking, then crop-level classification for full softmax vectors.

Detection answers \"where\"; classification answers \"which disease distribution\" per crop.
If `classifier_weights` is unset, emits a uniform probability vector over `class_names` (placeholder).
"""
