"""사전학습 분류 모델 생성 및 Grad-CAM용 타깃 레이어."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
from torchvision import models


def _replace_head(in_features: int, num_classes: int, dropout: float = 0.3) -> nn.Sequential:
    return nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(in_features, num_classes),
    )


def build_model(
    backbone: str,
    num_classes: int,
    pretrained: bool = True,
) -> tuple[nn.Module, Any]:
    """
    Returns:
        model, target_layer: Grad-CAM에 쓸 마지막 conv 블록 (ResNet: layer4, EfficientNet: features[-1])
    """
    weights = "DEFAULT" if pretrained else None
    backbone_l = backbone.lower().strip()

    if backbone_l == "resnet18":
        m = models.resnet18(weights=weights)
        in_f = m.fc.in_features
        m.fc = nn.Linear(in_f, num_classes)
        target = m.layer4
        return m, target

    if backbone_l == "resnet50":
        m = models.resnet50(weights=weights)
        in_f = m.fc.in_features
        m.fc = nn.Linear(in_f, num_classes)
        target = m.layer4
        return m, target

    if backbone_l == "efficientnet_b0":
        m = models.efficientnet_b0(weights=weights)
        in_f = m.classifier[1].in_features
        m.classifier = _replace_head(in_f, num_classes)
        target = m.features[-1]
        return m, target

    raise ValueError(f"지원하지 않는 backbone: {backbone} (resnet18, resnet50, efficientnet_b0)")


def freeze_backbone(model: nn.Module, backbone: str, freeze: bool) -> None:
    if not freeze:
        return
    b = backbone.lower().strip()
    if b in ("resnet18", "resnet50"):
        for name, p in model.named_parameters():
            if not name.startswith("fc"):
                p.requires_grad = False
    elif b == "efficientnet_b0":
        for name, p in model.named_parameters():
            if not name.startswith("classifier"):
                p.requires_grad = False
    else:
        for p in model.parameters():
            p.requires_grad = True


def unfreeze_all(model: nn.Module) -> None:
    for p in model.parameters():
        p.requires_grad = True
