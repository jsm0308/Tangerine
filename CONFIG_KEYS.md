# Configuration keys reference

프로젝트 개요·파이프라인 전체 설명: [`README.md`](../README.md), [`docs/PIPELINE.md`](../docs/PIPELINE.md).

All tunable parameters live in [`config.py`](config.py) as dataclasses. Override via [`configs/default_config.yaml`](configs/default_config.yaml) or `--config path.yaml`.

## `experiment`

| Key | Type | Description |
|-----|------|-------------|
| `experiment_id` | str | Folder name under `base_output_dir`; also `reports/{id}/`. |
| `base_output_dir` | str | Root for renders, augmented images, reports. |
| `seed` | int | RNG seed (Blender + augment; set `PYTHONHASHSEED` separately if needed). |
| `log_level` | str | Logging level for Python stages (`INFO`, `DEBUG`, …). |

## `blender`

| Key | Type | Description |
|-----|------|-------------|
| `blender_executable` | str | Path to `blender` binary; empty = `PATH`. |
| `assets_root` | str | Asset root (meshes/textures); default `data/Tangerine_3D`. |
| `citrus_count_min` / `citrus_count_max` | int | Random count of citrus spheres per episode. |
| `spawn_total` | int? | If set, fixed number of fruits (overrides min/max). |
| `spawn_rate_per_sec` | float | Reserved for streaming spawn. |
| `belt_speed` | float | Belt translation speed (units/s); feeds augment motion-blur hint. |
| `physics_substeps` | int | Rigid body solver substeps. |
| `rigid_body_friction_min/max` | float | Random friction range per fruit. |
| `rigid_body_restitution` | float | Bounciness. |
| `light_energy_min/max` | float | Point light energy range. |
| `light_location_jitter` | float | Max offset for light position. |
| `color_temperature_min/max` | float | Blackbody temperature range (K). |
| `camera_jitter_deg` | float | Random euler jitter on camera. |
| `camera_height_offset_min/max` | float | Camera Z offset range. |
| `citrus_initial_rotation_jitter_deg` | float | Random rotation on spawn. |
| `render_width` / `render_height` | int | Output resolution. |
| `render_fps` | int | Scene FPS. |
| `episode_frame_count` | int | Number of frames to render. |
| `texture_pools` | dict | Class name → list of texture/material ids (for future assets). |
| `renders_subdir` | str | Subfolder under experiment dir for PNG sequence. |
| `metadata_filename` | str | JSONL filename for GT + optional 2D bbox. |

## `augment`

| Key | Type | Description |
|-----|------|-------------|
| `input_subdir` | str | Usually `renders`. |
| `output_subdir` | str | Augmented frames (e.g. `renders_aug`). |
| `motion_blur_max_kernel` | int | Max kernel size (odd; clamped in code). |
| `motion_blur_probability` | float | Per-frame probability of applying blur. |
| `blur_direction_tied_to_belt` | bool | Blur along belt axis. |
| `belt_blur_angle_deg` | float | Motion blur direction in image plane. |
| `gaussian_noise_std_min/max` | float | Gaussian noise σ range. |
| `jpeg_quality_min/max` | int | JPEG quality if `jpeg` in `augment_order`. |
| `augment_order` | list[str] | Order of ops: `motion_blur`, `gaussian_noise`, `jpeg`. |

## `preprocess`

Phase 1: trigger mode and belt slot tagging (merged into `infer` unless `mode` is `passthrough`).  
Implementation package: `src/inference/preprocess/` (YAML key stays `preprocess`).

| Key | Type | Description |
|-----|------|-------------|
| `mode` | str | `simulation` (frame-sync ticks), `encoder_stub` (counter stub), `passthrough` (no `belt_slot_index`). |
| `mm_per_tick` | float | Logical distance per tick (metadata; e.g. mm). |
| `slots_count` | int | Horizontal bins for `belt_slot_index` from bbox center x. |
| `tick_stride_frames` | int | Ticks advanced per frame index in simulation trigger. |
| `attach_slots_during_inference` | bool | If false, skip slot assignment even if not passthrough. |
| `multi_camera_offsets` | list[int] | Slot offsets per camera (first index used for single camera). |
| `write_slot_events_jsonl` | bool | If true, write `slot_events_jsonl` alongside inference. |
| `slot_events_jsonl` | str | Filename under experiment dir for slot tick log. |

## `inference`

| Key | Type | Description |
|-----|------|-------------|
| `detection_backend` | str | `yolo_two_stage` (default), `yolo_unified`, `mask_rcnn_torchvision`. |
| `classifier_backend` | str | `yolo_cls`, `mobilenet_v3`, `none` (two-stage / mask-rcnn crop path). |
| `tracker_profile` | str | Empty = use `tracker` as-is. `botsort` / `bytetrack` map to built-in Ultralytics yaml. |
| `mobilenet_weights` | str | Optional `.pth` for MobileNetV3 head (see `classifiers.py`). |
| `mask_rcnn_weights` | str | Optional custom Mask R-CNN weights; empty = COCO pretrained. |
| `mask_rcnn_classify_crops` | bool | If false, Mask R-CNN path skips crop disease classifier (uniform probs). |
| `detector_weights` | str | Ultralytics detection `.pt` (YOLO backends). |
| `classifier_weights` | str | Ultralytics classification `.pt` for **full softmax**; empty → uniform fallback. |
| `device` | str | `cuda`, `cpu`, or empty for auto. |
| `cuda_visible_devices` | str | Sets `CUDA_VISIBLE_DEVICES` before import. |
| `conf_threshold` / `iou_threshold` | float | Detection thresholds (also IoU for internal IoU tracker in Mask R-CNN path). |
| `tracker` | str | e.g. `bytetrack.yaml` (used when `tracker_profile` is empty). |
| `cls_input_size` | int | Square crop resize for classifier. |
| `batch_size_inference` | int | Batch size for crop classification. |
| `alert_probability_threshold` | float | Red box if top disease prob ≥ this. |
| `stats_disease_threshold` | float | Count “detected disease” if prob ≥ this. |
| `class_names` | list[str] | Disease labels (order must match classifier). |
| `inference_input_subdir` | str | Usually `renders_aug`. |
| `predictions_jsonl` | str | Per-frame predictions log filename. |

## `report`

| Key | Type | Description |
|-----|------|-------------|
| `reports_subdir` | str | `reports` under experiment output. |
| `include_html` | bool | Generate `report.html` via Jinja2. |
| `crop_resize_max` | int | Max side for saved crop thumbnails. |
| `matplotlib_dpi` | int | Chart resolution. |

## Pipeline layout

```
{base_output_dir}/{experiment_id}/
  blender_config.json          # written for Blender subprocess
  {renders_subdir}/            # raw PNGs + frame_metadata.jsonl
  {renders_aug}/               # augmented PNGs
  {inference.predictions_jsonl}
  {postprocess.actuation_signals_jsonl}   # optional; after `--stage postprocess`
  {report.reports_subdir}/       # report.md, report.html, crops/, figures/
```
