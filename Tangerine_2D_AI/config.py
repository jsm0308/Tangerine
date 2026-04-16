"""학습·데이터 로딩 기본 설정."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrainConfig:
    """노트북 또는 스크립트에서 덮어쓸 수 있는 기본값."""

    # 경로: Colab에서 압축 해제 위치에 맞게 변경
    data_root: Path = Path("/content/Tangerine_2D")
    output_dir: Path = Path("/content/Tangerine_2D_runs")

    # 분할 비율 (합계 1.0): train / val / test
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15

    # 학습
    backbone: str = "resnet18"  # torchvision: resnet18 | resnet50 | efficientnet_b0
    image_size: int = 224
    batch_size: int = 32
    num_epochs: int = 30
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    num_workers: int = 2
    seed: int = 42

    # 선택: 처음 몇 에폭은 백본 동결 후 헤드만 학습
    freeze_backbone_epochs: int = 0

    # 이미지 확장자
    image_extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

    # TensorBoard / 체크포인트
    experiment_name: str = "tangerine_2d"
    # best.pt 선택: 고 acc만 믿기 어려울 때 val_f1_macro
    best_metric: str = "val_accuracy"  # val_accuracy | val_f1_macro

    # XAI: Grad-CAM 샘플 수 (테스트·검증에서 뽑는 총 장수 상한)
    xai_num_samples: int = 12

    def validate_split(self) -> None:
        s = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"train/val/test 비율 합이 1이 아님: {s}")
        allowed = ("val_accuracy", "val_f1_macro")
        if self.best_metric not in allowed:
            raise ValueError(f"best_metric은 {allowed} 중 하나여야 함: {self.best_metric!r}")

    def effective_output_dir(self) -> Path:
        return self.output_dir / self.experiment_name


def default_imagenet_normalize() -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
