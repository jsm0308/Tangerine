# Subfolder names under variant output_dir — match Track 2 (glb_from_2d) layout.
_DISEASE_TO_FOLDER = {
    "healthy": "healthy",
    "black_spot": "Black spot",
    "canker": "Canker",
    "greening": "Greening",
    "scab": "Scab",
}


def disease_output_folder(disease_key: str) -> str:
    """Map YAML `disease_params` key → subdirectory name (display casing)."""
    k = (disease_key or "").strip()
    if k in _DISEASE_TO_FOLDER:
        return _DISEASE_TO_FOLDER[k]
    return k.replace("_", " ").title()
