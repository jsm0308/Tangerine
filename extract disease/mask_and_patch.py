# -----------------------------------------------------------------------------
# 복사본 — 원본: 레포 루트 src/decal_prep/mask_and_patch.py
# Colab_From2D 단독 실행용. upstream 수정 시 동기화할 것.
# -----------------------------------------------------------------------------

"""
병변 영역 마스킹 → RGBA 패치 추출.

- SAM(Segment Anything): 선택 — checkpoint + segment_anything 설치 시 자동 마스크.
- 폴백: rembg 전경 + LAB/명도 기반 병변 후보 + 형태학.
- 경계: 거리 변환 기반 알파 페더 + (선택) seamlessClone(Poisson류)로 배경색 판에 합성.

산출: decal_cache_root 아래 클래스/이미지별 패치 PNG + manifest.json
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def load_decal_config_defaults() -> Dict[str, Any]:
    return {
        "enabled": True,
        "cache_dir": "Generate_Tangerine_3D/from_2d_track/decal_cache",
        "sam_checkpoint": "",
        "sam_model_type": "vit_b",
        # SAM 병렬: 1이면 순차. 2 이상이면 이미지를 N개 프로세스로 나누고 sam_cuda_devices 와 매칭
        "sam_parallel_gpus": 1,
        "sam_cuda_devices": "0",
        "max_masks_per_image": 6,
        "min_mask_area_ratio": 0.0012,
        "max_mask_area_ratio": 0.45,
        "patch_pad_px": 10,
        "alpha_feather_px": 6.0,
        "poisson_seamless_clone": True,
        "decals_per_asset": 4,
        "stamps_per_asset": 4,
        "texture_resolution": 2048,
        "stamp_uv_radius": 0.06,
        "use_healthy_albedo_base": True,
    }


def _safe_key(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    return s.strip() or "unnamed"


def _list_images(class_dir: Path) -> List[Path]:
    if not class_dir.is_dir():
        return []
    out: List[Path] = []
    for p in sorted(class_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in IMAGE_EXT:
            out.append(p)
    return out


def _rembg_mask_bgr(bgr: np.ndarray) -> np.ndarray:
    from rembg import remove
    from PIL import Image

    pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    out = remove(pil)  # RGBA
    arr = np.array(out)
    if arr.shape[2] < 4:
        return np.ones(bgr.shape[:2], dtype=np.uint8) * 255
    a = arr[:, :, 3]
    return a


def _heuristic_lesion_masks(
    bgr: np.ndarray,
    fg_mask: np.ndarray,
    min_area_ratio: float,
    max_area_ratio: float,
    max_masks: int,
) -> List[np.ndarray]:
    """전경 내부에서 어두운/이질 영역을 병변 후보로 분할."""
    h, w = bgr.shape[:2]
    fg = fg_mask > 128
    if not np.any(fg):
        return []

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].astype(np.float32)
    L_fg = L[fg]
    mu, sigma = float(np.mean(L_fg)), float(np.std(L_fg) + 1e-6)
    # 어두운 반점·병변 후보
    dark = (L < mu - 0.65 * sigma) & fg
    alt = np.zeros((h, w), dtype=np.uint8)
    alt[dark] = 255
    alt = cv2.morphologyEx(alt, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    alt = cv2.morphologyEx(alt, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(alt, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total = h * w
    min_a = int(total * min_area_ratio)
    max_a = int(total * max_area_ratio)
    masks: List[np.ndarray] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_a or area > max_a:
            continue
        m = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(m, [c], -1, 255, thickness=-1)
        m = cv2.bitwise_and(m, (fg_mask > 128).astype(np.uint8) * 255)
        if np.sum(m > 0) < min_a:
            continue
        masks.append(m.astype(bool))

    masks.sort(key=lambda x: -np.sum(x))
    return masks[:max_masks]


# 프로세스당 SAM 가중치만 재사용 (제너레이터는 이미지 크기별 min_mask_region_area 때문에 매번 생성)
_sam_model_cache: Optional[Tuple[str, str, Any]] = None  # (checkpoint, model_type, sam_module)


def _sam_masks(
    rgb: np.ndarray,
    checkpoint: str,
    model_type: str,
    min_area_ratio: float,
    max_area_ratio: float,
    max_masks: int,
) -> List[np.ndarray]:
    global _sam_model_cache
    try:
        import torch
        from segment_anything import SamAutomaticMaskGenerator, sam_model_registry
    except Exception:
        return []

    ck = Path(checkpoint)
    if not ck.is_file():
        return []

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ck_str = str(ck.resolve())
    if _sam_model_cache and _sam_model_cache[0] == ck_str and _sam_model_cache[1] == model_type:
        sam = _sam_model_cache[2]
    else:
        sam = sam_model_registry[model_type](checkpoint=ck_str)
        sam.to(device=device)
        _sam_model_cache = (ck_str, model_type, sam)

    try:
        gen = SamAutomaticMaskGenerator(
            sam,
            points_per_side=16,
            pred_iou_thresh=0.86,
            stability_score_thresh=0.92,
            min_mask_region_area=int(rgb.shape[0] * rgb.shape[1] * min_area_ratio),
        )
    except TypeError:
        gen = SamAutomaticMaskGenerator(sam)
    raw = gen.generate(rgb)
    h, w = rgb.shape[:2]
    total = h * w
    min_a = total * min_area_ratio
    max_a = total * max_area_ratio
    out: List[np.ndarray] = []
    for d in sorted(raw, key=lambda x: -x.get("area", 0)):
        seg = d.get("segmentation")
        if seg is None:
            continue
        m = np.asarray(seg, dtype=bool)
        a = int(np.sum(m))
        if a < min_a or a > max_a:
            continue
        out.append(m)
        if len(out) >= max_masks * 2:
            break
    return out[:max_masks]


def _feather_alpha(mask_255: np.ndarray, feather: float) -> np.ndarray:
    if feather <= 0.5:
        return mask_255
    inv = 255 - mask_255
    dist = cv2.distanceTransform((inv < 128).astype(np.uint8), cv2.DIST_L2, 5)
    t = np.clip(dist / feather, 0.0, 1.0)
    return (t * 255).astype(np.uint8)


def _seamless_patch(
    bgr: np.ndarray,
    lesion_mask: np.ndarray,
    feather: float,
    use_clone: bool,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    lesion_mask: bool HxW
    Returns crop BGRA, crop mask (for bbox).
    """
    h, w = bgr.shape[:2]
    m255 = (lesion_mask.astype(np.uint8) * 255)
    if not np.any(m255 > 0):
        ph = min(64, h)
        pw = min(64, w)
        empty = np.zeros((ph, pw, 4), dtype=np.uint8)
        return empty, np.zeros((ph, pw), dtype=np.uint8)

    # peel color from ring outside eroded lesion
    er = cv2.erode(m255, np.ones((5, 5), np.uint8), iterations=1)
    dil = cv2.dilate(m255, np.ones((9, 9), np.uint8), iterations=1)
    ring = ((dil > 0) & (er == 0)).astype(np.uint8) * 255
    ys, xs = np.where(ring > 0)
    if len(xs) > 40:
        med = np.median(bgr[ys, xs], axis=0)
    else:
        med = np.median(bgr.reshape(-1, 3), axis=0)

    work = bgr.copy()
    if use_clone:
        try:
            x0, y0, bw, bh = cv2.boundingRect(m255)
            cx, cy = x0 + bw // 2, y0 + bh // 2
            dst_plate = np.full_like(bgr, med)
            # OpenCV seamlessClone: mask must be 1-channel full image size
            blended = cv2.seamlessClone(
                bgr,
                dst_plate,
                m255,
                (int(cx), int(cy)),
                cv2.MIXED_CLONE,
            )
            work = blended
        except Exception:
            pass

    alpha = _feather_alpha(m255, feather)
    bgra = cv2.cvtColor(work, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = cv2.bitwise_and(alpha, m255)

    x, y, bw, bh = cv2.boundingRect(m255)
    pad = 2
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w, x + bw + pad)
    y2 = min(h, y + bh + pad)
    crop = bgra[y1:y2, x1:x2]
    cm = m255[y1:y2, x1:x2]
    return crop, cm


def _full_image_fallback_patch(bgr: np.ndarray, fg_alpha: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """마스크 실패 시 전경 알파만 적용한 패치 1장."""
    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = fg_alpha
    return bgra, fg_alpha


def _process_one_image(
    img_path: Path,
    rel_key: str,
    out_dir: Path,
    cfg: Dict[str, Any],
) -> List[str]:
    """패치 파일명(상대) 목록."""
    bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if bgr is None:
        return []

    h, w = bgr.shape[:2]
    fg_a = _rembg_mask_bgr(bgr)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    sam_ck = (cfg.get("sam_checkpoint") or "").strip()
    masks: List[np.ndarray] = []
    if sam_ck:
        masks = _sam_masks(
            rgb,
            sam_ck,
            str(cfg.get("sam_model_type") or "vit_b"),
            float(cfg.get("min_mask_area_ratio") or 0.0012),
            float(cfg.get("max_mask_area_ratio") or 0.45),
            int(cfg.get("max_masks_per_image") or 6),
        )

    if not masks:
        masks = _heuristic_lesion_masks(
            bgr,
            fg_a,
            float(cfg.get("min_mask_area_ratio") or 0.0012),
            float(cfg.get("max_mask_area_ratio") or 0.45),
            int(cfg.get("max_masks_per_image") or 6),
        )

    feather = float(cfg.get("alpha_feather_px") or 6.0)
    use_clone = bool(cfg.get("poisson_seamless_clone", True))

    patch_names: List[str] = []
    stem = _safe_key(img_path.stem)

    if masks:
        for mi, mbool in enumerate(masks):
            crop, _ = _seamless_patch(bgr, mbool, feather, use_clone)
            if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
                continue
            fname = f"{stem}__lesion_{mi:02d}.png"
            out_path = out_dir / fname
            cv2.imwrite(str(out_path), crop)
            patch_names.append(fname)
    else:
        bgra, _ = _full_image_fallback_patch(bgr, fg_a)
        fname = f"{stem}__full_{0:02d}.png"
        cv2.imwrite(str(out_dir / fname), bgra)
        patch_names.append(fname)

    return patch_names


def _chunk_jobs(
    jobs: List[Tuple[Path, str, Path, str]], n_workers: int
) -> List[List[Tuple[Path, str, Path, str]]]:
    if not jobs:
        return []
    n_workers = max(1, min(n_workers, len(jobs)))
    q, r = divmod(len(jobs), n_workers)
    out: List[List[Tuple[Path, str, Path, str]]] = []
    i = 0
    for k in range(n_workers):
        sz = q + (1 if k < r else 0)
        out.append(jobs[i : i + sz])
        i += sz
    return out


def _decal_worker_chunk(
    jobs_ser: List[Tuple[str, str, str, str]],
    decal_cfg: Dict[str, Any],
    cuda_dev: str,
) -> Dict[str, Any]:
    """spawn 워커: 프로세스마다 한 GPU만 보이게 한 뒤 이미지 청크 처리."""
    if cuda_dev.strip():
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_dev.strip()
    images: Dict[str, Any] = {}
    for img_path_s, rel, img_dir_s, cname in jobs_ser:
        img_path = Path(img_path_s)
        img_dir = Path(img_dir_s)
        patches = _process_one_image(img_path, rel, img_dir, decal_cfg)
        rel_patch_paths = [f"{cname}/{p}" for p in patches]
        images[rel] = {
            "absolute_source": str(img_path.resolve()),
            "patches": rel_patch_paths,
        }
    return images


@dataclass
class DecalCacheResult:
    manifest: Dict[str, Any]
    manifest_path: Path


def build_decal_cache(
    fruits_root: Path,
    cache_root: Path,
    decal_cfg: Dict[str, Any],
) -> DecalCacheResult:
    """
    fruits_root: ImageFolder 루트
    cache_root: 예) .../from_2d_track/decal_cache
    """
    fruits_root = fruits_root.resolve()
    cache_root = cache_root.resolve()
    cache_root.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "version": 1,
        "fruits_root": str(fruits_root),
        "cache_root": str(cache_root),
        "images": {},
    }

    sam_ck = (decal_cfg.get("sam_checkpoint") or "").strip()
    n_par = max(1, int(decal_cfg.get("sam_parallel_gpus") or 1))
    dev_str = (decal_cfg.get("sam_cuda_devices") or "0").strip()
    device_list = [x.strip() for x in dev_str.split(",") if x.strip()]
    if not device_list:
        device_list = ["0"]

    class_dirs = sorted([p for p in fruits_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    for class_dir in class_dirs:
        cname = _safe_key(class_dir.name)
        img_dir = cache_root / cname
        img_dir.mkdir(parents=True, exist_ok=True)

    jobs: List[Tuple[Path, str, Path, str]] = []
    for class_dir in class_dirs:
        cname = _safe_key(class_dir.name)
        img_dir = cache_root / cname
        for img_path in _list_images(class_dir):
            rel = f"{class_dir.name}/{img_path.name}"
            jobs.append((img_path, rel, img_dir, cname))

    use_mp = bool(sam_ck) and n_par > 1 and len(jobs) > 1
    if use_mp:
        n_workers = min(n_par, len(device_list), len(jobs))
        chunks = _chunk_jobs(jobs, n_workers)
        ctx = mp.get_context("spawn")
        starmap_args: List[Tuple[List[Tuple[str, str, str, str]], Dict[str, Any], str]] = []
        for wi, chunk in enumerate(chunks):
            if not chunk:
                continue
            cuda_dev = device_list[wi % len(device_list)]
            ser = [(str(a[0]), a[1], str(a[2]), a[3]) for a in chunk]
            starmap_args.append((ser, decal_cfg, cuda_dev))
        manifest_images: Dict[str, Any] = {}
        with ctx.Pool(processes=len(starmap_args)) as pool:
            results = pool.starmap(_decal_worker_chunk, starmap_args)
        for part in results:
            manifest_images.update(part)
        manifest["images"] = manifest_images
    else:
        for img_path, rel, img_dir, cname in jobs:
            patches = _process_one_image(img_path, rel, img_dir, decal_cfg)
            rel_patch_paths = [f"{cname}/{p}" for p in patches]
            manifest["images"][rel] = {
                "absolute_source": str(img_path.resolve()),
                "patches": rel_patch_paths,
            }

    man_path = cache_root / "manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return DecalCacheResult(manifest=manifest, manifest_path=man_path)
