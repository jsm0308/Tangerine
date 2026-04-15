# Tangerine_2D 이미지 분류 (Colab)

5개 클래스(`Black spot`, `Canker`, `Greening`, `healthy`, `Scab`) 감귤 2D 이미지를 **전이학습 CNN**으로 분류하고, **TensorBoard**로 학습 과정을 기록하며, **Grad-CAM**으로 모델이 주목한 영역을 시각화합니다.

## Colab에서 사용하는 방법 (zip 두 개)

1. **데이터** `Tangerine_2D` 폴더를 zip으로 압축해 Colab에 업로드·압축 해제합니다.  
   - 예: `/content/Tangerine_2D` 아래에 클래스 폴더 5개가 바로 보여야 합니다.
2. **코드** 이 폴더(`Tangerine_2D_AI`)를 zip으로 압축해 업로드·압축 해제합니다.  
   - 예: `/content/Tangerine_2D_AI`
3. 노트북 `train_tangerine_2d.ipynb`를 열고, **경로 셀**에서 `DATA_ROOT` / `PROJECT_ROOT`를 자신의 경로에 맞게 수정한 뒤 전체 실행합니다.

```text
/content/Tangerine_2D/
  Black spot/  *.jpg ...
  Canker/
  Greening/
  healthy/
  Scab/

/content/Tangerine_2D_AI/
  config.py
  data_loaders.py
  ...
  train_tangerine_2d.ipynb
```

## 산출물

기본 출력 디렉터리는 `output_dir/experiment_name`(설정: `TrainConfig.output_dir`, `experiment_name`)입니다.

| 항목 | 설명 |
|------|------|
| `tensorboard/` | 학습·검증 loss/accuracy, learning rate |
| `best.pt`, `last.pt` | 체크포인트 (테스트·Grad-CAM은 **best** 가중치 사용) |
| `class_to_idx.json`, `splits.json` | 클래스 매핑·분할에 사용한 경로(재현용) |
| `test_classification_report.txt`, `test_confusion_matrix.png` | 테스트셋 분류 리포트·혼동 행렬 |
| `gradcam/` | Grad-CAM 오버레이 PNG (파일명에 gt/pred 클래스 포함) |

Colab에서 TensorBoard:

```python
%load_ext tensorboard
%tensorboard --logdir /content/Tangerine_2D_runs/tangerine_2d/tensorboard
```

(`output_dir`를 바꿨다면 그 경로의 `tensorboard` 하위 폴더로 지정)

---

## 기술적 판단과 근거

### 1. PyTorch + torchvision

- 메인 Tangerine 레포가 PyTorch 기반이며, Colab GPU와의 호환 및 문서가 풍부합니다.
- `torchvision.models`의 사전학습 가중치(ImageNet)를 사용해 **적은 데이터**에서도 수렴이 빠른 편입니다.

### 2. 데이터: 클래스별 폴더 + 계층화 3분할

- 폴더 구조는 `torchvision.datasets.ImageFolder` 관례와 동일하게, **하위 폴더명 = 클래스 라벨**로 둡니다. (`healthy`와 `Black spot`처럼 대소문자 혼합은 **데이터와 동일한 문자열**을 유지합니다.)
- 사용자가 train/val/test를 미리 나누지 않았으므로, **한 번에 stratified split**으로 train / validation / test를 만듭니다.
- **Stratified** 이유: 클래스별 이미지 수가 다를 때 무작위 분할만 하면 특정 분할에 클래스가 치우칠 수 있어, 검증·테스트 지표가 왜곡될 수 있습니다. sklearn `train_test_split(..., stratify=...)`를 두 번 적용해 **기본 70% / 15% / 15%**에 맞춥니다.

### 3. Train / Validation / Test 역할

- **Train**: 가중치 업데이트.
- **Validation**: 에폭마다 일반화 성능 추정, **best 체크포인트** 선택 기준. 하이퍼파라미터를 반복 튜닝할 때는 **test를 보지 않고** val만 보는 것이 좋습니다(노트북 주석 참고).
- **Test**: 학습 종료 후 **한 번** 보고하는 최종 일반화 지표. 본 코드는 **best val** 가중치를 로드한 뒤 테스트셋을 평가합니다.

### 4. 모델: 사전학습 CNN (기본 `resnet18`)

- ResNet은 구조가 단순하고 Grad-CAM 타깃 레이어(`layer4`)가 명확합니다.
- 필요 시 `TrainConfig.backbone`을 `resnet50`, `efficientnet_b0`로 바꿀 수 있습니다(이미지 크기 224 가정).

### 5. 옵티마이저·스케줄

- **AdamW**: 가중치 감쇠(decoupled)가 잘 정리된 일반적 선택.
- **CosineAnnealingLR**: 학습률을 부드럽게 줄여 후반 미세 수렴을 돕습니다.
- **선택** `freeze_backbone_epochs`: 초반 몇 에폭은 백본을 고정하고 분류 헤드만 학습하는 **전이학습 관례**를 두었습니다. 기본값 `0`은 처음부터 전체를 학습합니다. `k>0`이면 **1~k 에폭**과 **k+1~N 에폭**으로 스케줄러를 나눕니다.

### 6. 증강 (train만)

- `RandomResizedCrop`, `RandomHorizontalFlip`, 약한 `ColorJitter`: 과적합 완화 및 촬영 변화에 대한 강건성.
- 검증·테스트는 **Resize + CenterCrop**으로 동일 조건에서 평가합니다.
- 정규화는 ImageNet 평균·분산(사전학습과 동일 스케일).

### 7. 로깅: TensorBoard

- 에폭별 train/val loss·accuracy, learning rate를 스칼라로 기록해 **곡선**으로 확인합니다.
- Colab 내장 TensorBoard UI로 별도 서버 없이 확인 가능합니다.

### 8. 설명가능 AI: Grad-CAM

- **Grad-CAM**은 타깃 클래스 점수에 대한 마지막 CNN feature map의 기울기를 가중합해 **공간 중요도 맵**을 만듭니다. “어느 부분을 보며 그 클래스라고 했는지”를 **히트맵**으로 볼 수 있습니다.
- 외부 패키지 의존을 줄이기 위해 **PyTorch 훅만으로 구현**했습니다.
- 시각화는 **예측 클래스**에 대한 CAM을 사용합니다(파일명에 gt/pred 모두 표기).

### 9. 재현성

- `random` / `numpy` / `torch` 시드 고정, 분할 시드 고정.
- `splits.json`에 분할된 경로·라벨을 저장해 동일 데이터로 재실험할 때 참고할 수 있습니다.

### 10. 의존성

- `requirements-notebook.txt`에 명시. PyTorch는 Colab 기본에 있을 수 있으나, CUDA 버전에 맞게 [pytorch.org](https://pytorch.org/)에서 재설치해도 됩니다.

---

## 문제 해결

- **CUDA 메모리 부족**: `batch_size` 또는 `image_size`를 줄입니다.
- **클래스 폴더를 찾을 수 없음**: `DATA_ROOT`가 `Tangerine_2D`를 가리키는지(그 안에 5개 폴더) 확인합니다.
- **import 오류**: 노트북의 `sys.path.insert(0, str(PROJECT_ROOT))`가 압축 해제된 `Tangerine_2D_AI` 루트를 가리키는지 확인합니다.
