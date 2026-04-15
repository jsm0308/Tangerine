"""
Inference: detection backends + tracking + disease probabilities + belt-slot preprocess.

- `pipeline.run_inference` — entry point (dispatches via `backends.dispatch_inference`).
- `preprocess` — triggers and `belt_slot_index` helpers (YAML key remains `preprocess`).
"""
