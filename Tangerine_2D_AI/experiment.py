"""전체 학습·평가·XAI 실행 (노트북에서 호출)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.tensorboard import SummaryWriter

from config import TrainConfig
from data_loaders import make_dataloaders, save_split_metadata, set_seed
from model_factory import build_model, freeze_backbone, unfreeze_all
from train_eval import (
    evaluate,
    load_checkpoint,
    metrics_report,
    save_checkpoint,
    train_one_epoch,
)
from xai_gradcam import save_gradcam_batch


def _plot_confusion_matrix(cm: np.ndarray, class_names: list[str], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(cm.shape[1]),
        yticks=np.arange(cm.shape[0]),
        xticklabels=class_names,
        yticklabels=class_names,
        ylabel="True",
        xlabel="Predicted",
        title="Confusion matrix",
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def run_training(cfg: TrainConfig) -> Path:
    cfg.validate_split()
    if cfg.freeze_backbone_epochs > cfg.num_epochs:
        raise ValueError(
            f"freeze_backbone_epochs({cfg.freeze_backbone_epochs})는 "
            f"num_epochs({cfg.num_epochs})보다 클 수 없습니다."
        )
    set_seed(cfg.seed)
    out = cfg.effective_output_dir()
    out.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, test_loader, meta = make_dataloaders(cfg)
    save_split_metadata(meta, out / "splits.json")

    class_names: list[str] = meta["class_names"]
    num_classes = len(class_names)
    with open(out / "class_to_idx.json", "w", encoding="utf-8") as f:
        json.dump(meta["class_to_idx"], f, ensure_ascii=False, indent=2)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, target_layer = build_model(cfg.backbone, num_classes, pretrained=True)
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    writer = SummaryWriter(log_dir=str(out / "tensorboard"))

    best_val_acc = 0.0
    best_epoch = 0
    global_step = 0

    def one_epoch(epoch_idx: int) -> None:
        nonlocal best_val_acc, best_epoch, global_step
        global_step += 1
        tr_loss, tr_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device, global_step, writer
        )
        va_loss, va_acc, _, _ = evaluate(
            model, val_loader, criterion, device, global_step, "val", writer
        )
        scheduler.step()
        writer.add_scalar("lr", optimizer.param_groups[0]["lr"], global_step)

        print(
            f"Epoch {epoch_idx}/{cfg.num_epochs} | "
            f"train loss {tr_loss:.4f} acc {tr_acc:.4f} | "
            f"val loss {va_loss:.4f} acc {va_acc:.4f}"
        )

        save_checkpoint(
            out / "last.pt",
            model,
            optimizer,
            epoch_idx,
            best_val_acc,
            {"class_names": class_names, "backbone": cfg.backbone},
        )
        if va_acc >= best_val_acc:
            best_val_acc = va_acc
            best_epoch = epoch_idx
            save_checkpoint(
                out / "best.pt",
                model,
                optimizer,
                epoch_idx,
                best_val_acc,
                {"class_names": class_names, "backbone": cfg.backbone},
            )

    k = cfg.freeze_backbone_epochs
    if k > 0:
        freeze_backbone(model, cfg.backbone, freeze=True)
        optimizer = AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
        )
        scheduler = CosineAnnealingLR(optimizer, T_max=max(k, 1))
        for e in range(1, k + 1):
            one_epoch(e)
        unfreeze_all(model)
        rem = cfg.num_epochs - k
        optimizer = AdamW(
            model.parameters(),
            lr=cfg.learning_rate * 0.1,
            weight_decay=cfg.weight_decay,
        )
        scheduler = CosineAnnealingLR(optimizer, T_max=max(rem, 1))
        for e in range(k + 1, cfg.num_epochs + 1):
            one_epoch(e)
    else:
        optimizer = AdamW(
            model.parameters(),
            lr=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
        )
        scheduler = CosineAnnealingLR(optimizer, T_max=max(cfg.num_epochs, 1))
        for e in range(1, cfg.num_epochs + 1):
            one_epoch(e)

    print(f"\nBest val acc: {best_val_acc:.4f} at epoch {best_epoch}")
    print("Loading best weights for test set & XAI...")
    load_checkpoint(out / "best.pt", model, device)

    _, _, y_pred, y_true = evaluate(
        model, test_loader, criterion, device, global_step, "test", writer
    )
    writer.close()
    report, cm = metrics_report(y_true, y_pred, class_names)
    print("\n=== Test classification report ===\n", report)
    (out / "test_classification_report.txt").write_text(report, encoding="utf-8")
    _plot_confusion_matrix(cm, class_names, out / "test_confusion_matrix.png")

    # Grad-CAM: 테스트 배치 일부
    xai_dir = out / "gradcam"
    model.eval()
    it = iter(test_loader)
    batch = next(it)
    imgs, labs = batch[0], batch[1]
    save_gradcam_batch(
        model,
        target_layer,
        imgs,
        labs,
        class_names,
        xai_dir,
        device,
        max_samples=cfg.xai_num_samples,
    )
    print(f"Grad-CAM images saved under {xai_dir}")

    return out
