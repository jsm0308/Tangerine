"""Tangerine_2D 폴더(클래스별 하위 디렉터리)에서 이미지 수집 및 계층화 train/val/test 분할."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from config import TrainConfig, default_imagenet_normalize


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def collect_images(
    data_root: Path,
    extensions: tuple[str, ...],
) -> tuple[list[Path], list[int], list[str]]:
    """
    data_root 아래 각 하위 폴더명을 클래스로 본다.
    클래스 순서는 정렬된 폴더명과 동일 (ImageFolder와 유사).
    """
    data_root = Path(data_root)
    if not data_root.is_dir():
        raise FileNotFoundError(f"데이터 루트가 없습니다: {data_root}")

    class_dirs = sorted([d for d in data_root.iterdir() if d.is_dir()])
    if not class_dirs:
        raise ValueError(f"클래스 폴더가 없습니다: {data_root}")

    class_names = [d.name for d in class_dirs]
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    paths: list[Path] = []
    labels: list[int] = []
    for d in class_dirs:
        label = class_to_idx[d.name]
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in extensions:
                paths.append(p)
                labels.append(label)

    if not paths:
        raise ValueError(f"이미지 파일이 없습니다: {data_root}")

    return paths, labels, class_names


def stratified_train_val_test(
    paths: list[Path],
    labels: list[int],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[list[Path], list[int], list[Path], list[int], list[Path], list[int]]:
    """계층화 3분할. 기본 70/15/15."""
    s = train_ratio + val_ratio + test_ratio
    if abs(s - 1.0) > 1e-6:
        raise ValueError(f"분할 비율 합이 1이 아님: {s}")

    test_size = test_ratio
    # 남은 비율에서 val이 차지하는 비율 = val / (train + val)
    val_of_remainder = val_ratio / (train_ratio + val_ratio)

    paths_tv, paths_te, y_tv, y_te = train_test_split(
        paths,
        labels,
        test_size=test_size,
        stratify=labels,
        random_state=seed,
    )
    paths_tr, paths_va, y_tr, y_va = train_test_split(
        paths_tv,
        y_tv,
        test_size=val_of_remainder,
        stratify=y_tv,
        random_state=seed,
    )
    return paths_tr, y_tr, paths_va, y_va, paths_te, y_te


class ImagePathDataset(Dataset):
    """경로 리스트 + 정수 라벨."""

    def __init__(
        self,
        paths: list[Path],
        labels: list[int],
        transform: transforms.Compose,
    ) -> None:
        self.paths = paths
        self.labels = labels
        self.transform = transform

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        p = self.paths[idx]
        try:
            img = Image.open(p).convert("RGB")
        except OSError as e:
            raise OSError(f"이미지 로드 실패: {p}") from e
        return self.transform(img), self.labels[idx]


def build_transforms(
    image_size: int,
    train: bool,
) -> transforms.Compose:
    mean, std = default_imagenet_normalize()
    if train:
        return transforms.Compose(
            [
                transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0)),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(0.1, 0.1, 0.1, 0.05),
                transforms.ToTensor(),
                transforms.Normalize(mean, std),
            ]
        )
    return transforms.Compose(
        [
            transforms.Resize(int(image_size * 1.14)),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ]
    )


def make_dataloaders(
    cfg: TrainConfig,
) -> tuple[DataLoader, DataLoader, DataLoader, dict[str, Any]]:
    cfg.validate_split()
    set_seed(cfg.seed)

    paths, labels, class_names = collect_images(cfg.data_root, cfg.image_extensions)
    paths_tr, y_tr, paths_va, y_va, paths_te, y_te = stratified_train_val_test(
        paths,
        labels,
        cfg.train_ratio,
        cfg.val_ratio,
        cfg.test_ratio,
        cfg.seed,
    )

    n_cls = len(class_names)
    for split_name, y_split in (
        ("train", y_tr),
        ("val", y_va),
        ("test", y_te),
    ):
        present = set(y_split)
        missing = set(range(n_cls)) - present
        if missing:
            miss_names = [class_names[i] for i in sorted(missing)]
            print(
                f"WARNING: '{split_name}' 분할에 샘플이 없는 클래스 인덱스 {sorted(missing)} "
                f"({miss_names}). 클래스당 이미지 수를 늘리거나 분할 비율을 조정하세요."
            )

    class_to_idx = {n: i for i, n in enumerate(class_names)}
    meta: dict[str, Any] = {
        "class_names": class_names,
        "class_to_idx": class_to_idx,
        "counts": {
            "total": len(paths),
            "train": len(paths_tr),
            "val": len(paths_va),
            "test": len(paths_te),
        },
    }

    ds_tr = ImagePathDataset(paths_tr, y_tr, build_transforms(cfg.image_size, train=True))
    ds_va = ImagePathDataset(paths_va, y_va, build_transforms(cfg.image_size, train=False))
    ds_te = ImagePathDataset(paths_te, y_te, build_transforms(cfg.image_size, train=False))

    common = dict(
        batch_size=cfg.batch_size,
        num_workers=cfg.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    train_loader = DataLoader(ds_tr, shuffle=True, drop_last=False, **common)
    val_loader = DataLoader(ds_va, shuffle=False, drop_last=False, **common)
    test_loader = DataLoader(ds_te, shuffle=False, drop_last=False, **common)

    meta["paths_split"] = {
        "train": [str(p) for p in paths_tr],
        "val": [str(p) for p in paths_va],
        "test": [str(p) for p in paths_te],
    }
    meta["labels_split"] = {
        "train": y_tr,
        "val": y_va,
        "test": y_te,
    }

    return train_loader, val_loader, test_loader, meta


def save_split_metadata(meta: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # labels는 리스트로 JSON 직렬화
    out = {
        "class_names": meta["class_names"],
        "class_to_idx": {k: int(v) for k, v in meta["class_to_idx"].items()},
        "counts": meta["counts"],
        "paths_split": meta["paths_split"],
        "labels_split": {
            k: [int(x) for x in v] for k, v in meta["labels_split"].items()
        },
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
