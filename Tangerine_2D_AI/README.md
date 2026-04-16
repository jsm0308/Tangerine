# Tangerine_2D 이미지 분류 (Colab)

5개 클래스(`Black spot`, `Canker`, `Greening`, `healthy`, `Scab`) 감귤 2D 이미지를 **전이학습 CNN**으로 분류하고, **TensorBoard**로 학습 과정을 기록하며, **Grad-CAM**으로 모델이 주목한 영역을 시각화합니다.

## Colab에서 사용하는 방법

1. **노트북만 먼저 연다** — Colab **파일 → 노트북 업로드**로 `train_tangerine_2d.ipynb`만 올려도 된다 (코드 zip을 먼저 풀 필요 없음).
2. 왼쪽 **파일** 패널에 `Tangerine_2D.zip`, `Tangerine_2D_AI.zip` 을 업로드한다 (또는 Drive에 두고 마운트).
3. **런타임 → 모두 실행** 또는 위에서부터 셀 순서대로 실행. 첫 코드 셀(§1)이 zip이 있으면 `/content`에 풀고, **`Tangerine_2D_AI/config.py`·데이터 폴더 위치를 자동 탐지**한다 (`colab_paths.py`). zip 안에 `Tangerine_2D_AI/Tangerine_2D_AI/` 처럼 이름이 한 겹 더 있어도 수동으로 옮길 필요 없다.
4. 학습·테스트 분리: 기본 **`run_training(cfg, run_final_eval=False)`** 후 **`run_test_only(cfg)`**. 한 번에 끝내려면 `run_final_eval=True` (비권장).

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

## 모델 아키텍처 (한눈에)

- **무엇을 하나요?** 이미지 한 장을 넣으면 **클래스 번호 하나**를 내는 **분류 네트워크**입니다. (합성·실사 감귤 이미지 → 5개 병해/정상 중 하나)

- **기본 모델 (`backbone="resnet18"`)**  
  - **ResNet-18**: 앞부분은 합성곱으로 특징을 뽑고, 끝에서 **전역 평균 풀링 → 완전연결층(fc)** 으로 점수를 냅니다.  
  - **ImageNet**으로 미리 학습된 가중치를 가져온 뒤, **마지막 `fc`만** 우리 클래스 개수(예: 5)에 맞게 **한 겹 선형층**으로 바꿉니다. 나머지 층은 그대로 두고 같이 학습합니다(전이학습).

- **입력**  
  - RGB 이미지, 보통 **224×224**로 맞춘 뒤 모델에 넣습니다.

- **다른 백본 (`TrainConfig.backbone`)**  
  - `resnet50`: 더 깊은 ResNet, 마찬가지로 마지막 `fc`만 클래스 수에 맞게 교체.  
  - `efficientnet_b0`: 효율적인 CNN, 마지막 분류기 부분만 **Dropout + 선형층**으로 교체.

- **Grad-CAM**  
  - ResNet은 마지막 합성곱 블록 **`layer4`**, EfficientNet은 **`features`의 마지막 블록**을 써서 “어디를 보며 판단했는지” 히트맵을 만듭니다.

구현 위치: [`model_factory.py`](model_factory.py) 의 `build_model`.

## 산출물

기본 출력 디렉터리는 `output_dir/experiment_name`(설정: `TrainConfig.output_dir`, `experiment_name`)입니다.

| 항목 | 설명 |
|------|------|
| `training_summary.json` | 학습 종료 시 저장(베스트 에폭·val acc/F1·시드·데이터 경로). `run_final_eval=False`여도 §4 끝에 생성 |
| `tensorboard/` | 학습·검증 loss/accuracy, **F1 macro·weighted·micro**, learning rate |
| `best.pt`, `last.pt` | 체크포인트 (`best_val_acc`, `best_val_f1_macro` 포함). `TrainConfig.best_metric`으로 best 선택 (`val_accuracy` 또는 `val_f1_macro`) |
| `class_to_idx.json`, `splits.json` | 클래스 매핑·분할에 사용한 경로(재현용) |
| `test_metrics.json`, `test_predictions.csv` | 테스트 F1·혼동 행렬(JSON)·샘플별 예측(CSV). `run_test_only` 또는 `run_training(..., run_final_eval=True)` 시 |
| `test_classification_report.txt`, `test_confusion_matrix.png` | 테스트셋 리포트(상단에 F1 요약)·혼동 행렬 |
| `gradcam/` | Grad-CAM 오버레이 PNG (파일명에 gt/pred 클래스 포함). **§4만 실행 시 없음** — `run_test_only` 필요 |
| (선택) `*_bundle.zip` | `experiment.zip_run_directory(effective_output_dir)` 로 실험 폴더 통째 압축 |

Colab에서 TensorBoard:

```python
%load_ext tensorboard
%tensorboard --logdir /content/Tangerine_2D_runs/tangerine_2d/tensorboard
```

(`output_dir`를 바꿨다면 그 경로의 `tensorboard` 하위 폴더로 지정)

### Colab에서 결과가 “날아간” 경우

- `/content`는 **런타임 종료 시 지워질 수 있음**. 중요한 산출물은 **`output_dir`를 Google Drive에 두거나**, 주기적으로 **`best.pt`** 등을 Drive로 복사해 두는 것을 권장합니다.
- **학습은 끝났는데** 마지막 테스트 리포트 단계에서만 오류가 났다면, 같은 `cfg`로 데이터·시드를 맞춘 뒤 **`run_test_only(cfg)`** 만 다시 실행할 수 있습니다 (`experiment`에서 import). `best.pt` 경로를 넘기려면 `run_test_only(cfg, Path("/path/to/best.pt"))`.

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

- 구조 요약은 위 **[모델 아키텍처 (한눈에)](#모델-아키텍처-한눈에)** 절을 본다.
- ResNet은 Grad-CAM 타깃(`layer4`)이 명확하고, 기본 실험에 무난합니다.
- `TrainConfig.backbone`으로 `resnet50`, `efficientnet_b0` 선택 가능(입력 224 가정).

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
