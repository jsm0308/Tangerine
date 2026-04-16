"""학습·검증 루프, 테스트 평가, 체크포인트."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm


def compute_f1_scores(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    num_classes: int,
) -> dict[str, float]:
    """macro / weighted / micro F1."""
    labels = list(range(num_classes))
    return {
        "f1_macro": float(
            f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)
        ),
        "f1_micro": float(
            f1_score(y_true, y_pred, labels=labels, average="micro", zero_division=0)
        ),
    }


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    epoch: int,
    num_classes: int,
    writer: SummaryWriter | None = None,
) -> tuple[float, float, dict[str, float]]:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    all_preds: list[int] = []
    all_labels: list[int] = []
    for x, y in tqdm(loader, desc=f"train e{epoch}", leave=False):
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * x.size(0)
        pred = logits.argmax(dim=1)
        correct += (pred == y).sum().item()
        total += x.size(0)
        all_preds.extend(pred.cpu().numpy().tolist())
        all_labels.extend(y.cpu().numpy().tolist())
    avg_loss = total_loss / max(total, 1)
    acc = correct / max(total, 1)
    y_t = np.array(all_labels)
    y_p = np.array(all_preds)
    f1 = compute_f1_scores(y_t, y_p, num_classes)
    if writer is not None:
        writer.add_scalar("train/loss", avg_loss, epoch)
        writer.add_scalar("train/accuracy", acc, epoch)
        writer.add_scalar("train/f1_macro", f1["f1_macro"], epoch)
        writer.add_scalar("train/f1_weighted", f1["f1_weighted"], epoch)
        writer.add_scalar("train/f1_micro", f1["f1_micro"], epoch)
    return avg_loss, acc, f1


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    epoch: int,
    split_name: str,
    num_classes: int,
    writer: SummaryWriter | None = None,
) -> tuple[float, float, np.ndarray, np.ndarray, dict[str, float]]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    all_preds: list[int] = []
    all_labels: list[int] = []
    for x, y in tqdm(loader, desc=f"{split_name} e{epoch}", leave=False):
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)
        logits = model(x)
        loss = criterion(logits, y)
        total_loss += loss.item() * x.size(0)
        pred = logits.argmax(dim=1)
        correct += (pred == y).sum().item()
        total += x.size(0)
        all_preds.extend(pred.cpu().numpy().tolist())
        all_labels.extend(y.cpu().numpy().tolist())
    avg_loss = total_loss / max(total, 1)
    acc = correct / max(total, 1)
    y_t = np.array(all_labels)
    y_p = np.array(all_preds)
    f1 = compute_f1_scores(y_t, y_p, num_classes)
    if writer is not None:
        writer.add_scalar(f"{split_name}/loss", avg_loss, epoch)
        writer.add_scalar(f"{split_name}/accuracy", acc, epoch)
        writer.add_scalar(f"{split_name}/f1_macro", f1["f1_macro"], epoch)
        writer.add_scalar(f"{split_name}/f1_weighted", f1["f1_weighted"], epoch)
        writer.add_scalar(f"{split_name}/f1_micro", f1["f1_micro"], epoch)
    return avg_loss, acc, y_p, y_t, f1


def save_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    best_val_acc: float,
    best_val_f1_macro: float,
    meta: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "best_val_acc": best_val_acc,
            "best_val_f1_macro": best_val_f1_macro,
            "meta": meta,
        },
        path,
    )


def metrics_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str],
) -> tuple[str, np.ndarray, dict[str, float]]:
    num_classes = len(class_names)
    f1 = compute_f1_scores(y_true, y_pred, num_classes)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))
    label_idx = list(range(num_classes))
    report = classification_report(
        y_true,
        y_pred,
        labels=label_idx,
        target_names=class_names,
        digits=4,
        zero_division=0,
    )
    header = (
        "=== F1 (sklearn) ===\n"
        f"macro: {f1['f1_macro']:.4f} | weighted: {f1['f1_weighted']:.4f} | micro: {f1['f1_micro']:.4f}\n"
        "(아래 classification_report의 f1-score 열은 클래스별·macro avg·weighted avg를 포함합니다.)\n\n"
        "=== classification_report ===\n"
    )
    return header + report, cm, f1


def load_checkpoint(path: Path, model: nn.Module, device: torch.device) -> dict[str, Any]:
    try:
        ckpt = torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        ckpt = torch.load(path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    return ckpt
