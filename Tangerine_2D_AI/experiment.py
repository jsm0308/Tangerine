"""전체 학습·평가·XAI 실행 (노트북에서 호출)."""

from __future__ import annotations

import csv
import json
import shutil
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


def save_training_summary(
    out: Path,
    cfg: TrainConfig,
    best_epoch: int,
    best_val_acc: float,
    best_val_f1_macro: float,
) -> None:
    """학습 종료 후 재현에 쓸 메타(JSON)."""
    payload = {
        "experiment_name": cfg.experiment_name,
        "backbone": cfg.backbone,
        "best_metric": cfg.best_metric,
        "best_epoch": best_epoch,
        "best_val_accuracy": best_val_acc,
        "best_val_f1_macro": best_val_f1_macro,
        "num_epochs": cfg.num_epochs,
        "seed": cfg.seed,
        "data_root": str(cfg.data_root),
        "effective_output_dir": str(out),
    }
    (out / "training_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_test_artifacts(
    out: Path,
    class_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
    test_f1: dict[str, float],
    cm: np.ndarray,
) -> None:
    """테스트 수치·혼동행렬·샘플별 예측을 파일로 저장."""
    (out / "test_metrics.json").write_text(
        json.dumps(
            {
                "class_names": class_names,
                "metrics": test_f1,
                "num_samples": int(len(y_true)),
                "confusion_matrix": cm.tolist(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with (out / "test_predictions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "y_true", "y_pred", "true_class", "pred_class"])
        for i, (yt, yp) in enumerate(zip(y_true, y_pred)):
            w.writerow(
                [
                    i,
                    int(yt),
                    int(yp),
                    class_names[int(yt)],
                    class_names[int(yp)],
                ]
            )


def zip_run_directory(run_dir: Path, zip_path: Path | None = None) -> Path:
    """
    학습 산출 폴더 전체를 zip으로 묶는다 (Colab에서 Drive 복사·다운로드용).
    `run_dir`은 `cfg.effective_output_dir()` 와 동일하게 지정.
    """
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"폴더 없음: {run_dir}")
    parent = run_dir.parent
    name = run_dir.name
    if zip_path is None:
        dest_base = str(parent / f"{name}_bundle")
    else:
        zip_path = zip_path.resolve()
        dest_base = str(zip_path.with_suffix(""))
    arc = shutil.make_archive(dest_base, "zip", root_dir=str(parent), base_dir=name)
    return Path(arc)


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


def run_training(cfg: TrainConfig, run_final_eval: bool = False) -> Path:
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

    best_epoch = 0
    best_primary = -1.0
    best_snap_val_acc = 0.0
    best_snap_val_f1 = 0.0
    global_step = 0

    def one_epoch(epoch_idx: int) -> None:
        nonlocal best_epoch, best_primary, best_snap_val_acc, best_snap_val_f1, global_step
        global_step += 1
        tr_loss, tr_acc, tr_f1 = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
            global_step,
            num_classes,
            writer,
        )
        va_loss, va_acc, _, _, va_f1 = evaluate(
            model,
            val_loader,
            criterion,
            device,
            global_step,
            "val",
            num_classes,
            writer,
        )
        scheduler.step()
        writer.add_scalar("lr", optimizer.param_groups[0]["lr"], global_step)

        print(
            f"Epoch {epoch_idx}/{cfg.num_epochs} | "
            f"train loss {tr_loss:.4f} acc {tr_acc:.4f} F1m {tr_f1['f1_macro']:.4f} | "
            f"val loss {va_loss:.4f} acc {va_acc:.4f} F1m {va_f1['f1_macro']:.4f}"
        )

        improved = False
        if cfg.best_metric == "val_f1_macro":
            if va_f1["f1_macro"] >= best_primary:
                improved = True
                best_primary = va_f1["f1_macro"]
        else:
            if va_acc >= best_primary:
                improved = True
                best_primary = va_acc

        if improved:
            best_epoch = epoch_idx
            best_snap_val_acc = va_acc
            best_snap_val_f1 = va_f1["f1_macro"]

        save_checkpoint(
            out / "last.pt",
            model,
            optimizer,
            epoch_idx,
            best_snap_val_acc,
            best_snap_val_f1,
            {
                "class_names": class_names,
                "backbone": cfg.backbone,
                "best_metric": cfg.best_metric,
            },
        )
        if improved:
            save_checkpoint(
                out / "best.pt",
                model,
                optimizer,
                epoch_idx,
                best_snap_val_acc,
                best_snap_val_f1,
                {
                    "class_names": class_names,
                    "backbone": cfg.backbone,
                    "best_metric": cfg.best_metric,
                },
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

    metric_label = "val macro F1" if cfg.best_metric == "val_f1_macro" else "val acc"
    metric_val = best_snap_val_f1 if cfg.best_metric == "val_f1_macro" else best_snap_val_acc
    print(
        f"\nBest ({metric_label}): {metric_val:.4f} at epoch {best_epoch} | "
        f"at that epoch — val acc {best_snap_val_acc:.4f}, val F1 macro {best_snap_val_f1:.4f}"
    )
    writer.close()

    save_training_summary(out, cfg, best_epoch, best_snap_val_acc, best_snap_val_f1)
    print(f"학습 요약 저장: {out / 'training_summary.json'}")

    if not run_final_eval:
        print(
            "테스트·Grad-CAM은 건너뜀 (run_final_eval=False). "
            "다음 셀에서 run_test_only(cfg)를 실행하세요."
        )
        return out

    print("Loading best weights for test set & XAI...")
    load_checkpoint(out / "best.pt", model, device)

    writer_tb = SummaryWriter(log_dir=str(out / "tensorboard"))
    _, _, y_pred, y_true, test_f1 = evaluate(
        model,
        test_loader,
        criterion,
        device,
        global_step,
        "test",
        num_classes,
        writer_tb,
    )
    writer_tb.close()
    report, cm, _ = metrics_report(y_true, y_pred, class_names)
    print("\n=== Test classification report ===\n", report)
    print(
        f"Test F1 — macro: {test_f1['f1_macro']:.4f}, "
        f"weighted: {test_f1['f1_weighted']:.4f}, micro: {test_f1['f1_micro']:.4f}"
    )
    (out / "test_classification_report.txt").write_text(report, encoding="utf-8")
    _plot_confusion_matrix(cm, class_names, out / "test_confusion_matrix.png")
    save_test_artifacts(out, class_names, y_true, y_pred, test_f1, cm)
    print(f"테스트 메트릭·예측 CSV 저장: {out / 'test_metrics.json'}, {out / 'test_predictions.csv'}")

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


def run_test_only(
    cfg: TrainConfig,
    checkpoint_path: Path | None = None,
) -> Path:
    """
    학습 없이 체크포인트만 로드해 테스트·리포트·Grad-CAM만 실행.
    Colab 세션이 끊겨 학습은 끝났는데 리포트 단계에서만 실패한 경우,
    `best.pt`를 Drive 등에 백업해 두었다면 같은 `cfg`·데이터로 재실행할 수 있다.
    """
    cfg.validate_split()
    set_seed(cfg.seed)
    out = cfg.effective_output_dir()
    out.mkdir(parents=True, exist_ok=True)

    _, _, test_loader, meta = make_dataloaders(cfg)
    class_names: list[str] = meta["class_names"]
    num_classes = len(class_names)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, target_layer = build_model(cfg.backbone, num_classes, pretrained=True)
    model = model.to(device)

    ckpt_path = checkpoint_path if checkpoint_path is not None else out / "best.pt"
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"체크포인트 없음: {ckpt_path}")
    print(f"Loading {ckpt_path} ...")
    load_checkpoint(ckpt_path, model, device)

    criterion = nn.CrossEntropyLoss()
    _, _, y_pred, y_true, test_f1 = evaluate(
        model,
        test_loader,
        criterion,
        device,
        0,
        "test",
        num_classes,
        writer=None,
    )
    report, cm, _ = metrics_report(y_true, y_pred, class_names)
    print("\n=== Test classification report ===\n", report)
    print(
        f"Test F1 — macro: {test_f1['f1_macro']:.4f}, "
        f"weighted: {test_f1['f1_weighted']:.4f}, micro: {test_f1['f1_micro']:.4f}"
    )
    (out / "test_classification_report.txt").write_text(report, encoding="utf-8")
    _plot_confusion_matrix(cm, class_names, out / "test_confusion_matrix.png")
    save_test_artifacts(out, class_names, y_true, y_pred, test_f1, cm)
    print(f"테스트 메트릭·예측 CSV 저장: {out / 'test_metrics.json'}, {out / 'test_predictions.csv'}")

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
