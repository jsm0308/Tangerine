"""순수 PyTorch Grad-CAM: 분류 점수에 대한 마지막 conv feature의 기여도 히트맵."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn


class GradCAM:
    """단일 타깃 레이어에 대한 Grad-CAM."""

    def __init__(self, model: nn.Module, target_layer: nn.Module) -> None:
        self.model = model
        self.target_layer = target_layer
        self.gradients: torch.Tensor | None = None
        self.activations: torch.Tensor | None = None
        self._fwd_handle = target_layer.register_forward_hook(self._forward_hook)
        self._bwd_handle = target_layer.register_full_backward_hook(self._backward_hook)

    def _forward_hook(self, _m, _inp, out: torch.Tensor) -> None:
        self.activations = out.detach()

    def _backward_hook(self, _m, _gi, go: tuple[torch.Tensor, ...]) -> None:
        if go[0] is not None:
            self.gradients = go[0].detach()

    def remove(self) -> None:
        self._fwd_handle.remove()
        self._bwd_handle.remove()

    def __call__(
        self,
        input_tensor: torch.Tensor,
        class_idx: int | None = None,
    ) -> tuple[np.ndarray, int]:
        """
        Returns:
            cam_hw: float32 [H, W] normalized to 0..1 (for visualization)
            pred_idx: 모델 argmax 클래스 (표시용)
        """
        self.model.eval()
        input_tensor = input_tensor.clone().requires_grad_(True)
        out = self.model(input_tensor)
        pred_idx = int(out.argmax(dim=1).item())
        if class_idx is None:
            class_idx = pred_idx
        score = out[:, class_idx].sum()
        self.model.zero_grad(set_to_none=True)
        score.backward(retain_graph=False)

        if self.gradients is None or self.activations is None:
            raise RuntimeError("Grad-CAM hooks did not capture gradients/activations")

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)  # GAP of gradients
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        cam = cam.squeeze(1).squeeze(0)
        cam_np = cam.cpu().numpy().astype(np.float32)
        cam_np = np.maximum(cam_np, 0)
        cmin, cmax = cam_np.min(), cam_np.max()
        if cmax - cmin > 1e-8:
            cam_np = (cam_np - cmin) / (cmax - cmin)
        else:
            cam_np = np.zeros_like(cam_np)
        return cam_np, pred_idx


def upsample_cam_to_image(
    cam_hw: np.ndarray,
    image_hw: tuple[int, int],
) -> np.ndarray:
    h, w = image_hw
    cam_u = cv2.resize(cam_hw, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(cam_u, 0.0, 1.0)


def overlay_heatmap(
    rgb_uint8: np.ndarray,
    cam_hw: np.ndarray,
    alpha: float = 0.45,
) -> np.ndarray:
    """rgb_uint8 [H,W,3], cam_hw same H,W in 0..1 -> BGR uint8 for OpenCV imwrite."""
    heat = (cam_hw * 255).astype(np.uint8)
    heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    heat_color = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
    blended = (alpha * heat_color + (1.0 - alpha) * rgb_uint8).astype(np.uint8)
    return cv2.cvtColor(blended, cv2.COLOR_RGB2BGR)


def denormalize_imagenet_tensor(
    tensor_chw: torch.Tensor,
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
    std: tuple[float, float, float] = (0.229, 0.224, 0.225),
) -> np.ndarray:
    """[3,H,W] normalized -> uint8 RGB [H,W,3]."""
    t = tensor_chw.detach().cpu().float()
    m = torch.tensor(mean).view(3, 1, 1)
    s = torch.tensor(std).view(3, 1, 1)
    x = t * s + m
    x = x.clamp(0, 1).numpy().transpose(1, 2, 0)
    return (x * 255).astype(np.uint8)


def save_gradcam_batch(
    model: nn.Module,
    target_layer: nn.Module,
    images: torch.Tensor,
    labels: torch.Tensor,
    class_names: list[str],
    out_dir: Path,
    device: torch.device,
    max_samples: int = 12,
) -> list[Path]:
    """
    images: batch [N,3,H,W] on CPU or device (will move)
    labels: [N] ground truth indices
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cam_engine = GradCAM(model, target_layer)
    saved: list[Path] = []
    n = min(images.size(0), max_samples)
    try:
        for i in range(n):
            x = images[i : i + 1].to(device)
            y_true = int(labels[i].item())

            cam, pred = cam_engine(x, class_idx=None)
            rgb = denormalize_imagenet_tensor(images[i])
            h, w = rgb.shape[:2]
            cam_resized = upsample_cam_to_image(cam, (h, w))
            bgr = overlay_heatmap(rgb, cam_resized)
            fname = (
                f"sample{i:02d}_gt_{class_names[y_true]}_pred_{class_names[pred]}.png"
            )
            # 파일명에 공백·슬래시 제거
            safe = fname.replace(" ", "_").replace("/", "_")
            path = out_dir / safe
            cv2.imwrite(str(path), bgr)
            saved.append(path)
    finally:
        cam_engine.remove()
    return saved
