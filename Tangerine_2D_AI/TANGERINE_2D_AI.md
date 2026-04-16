# Tangerine_2D 이미지 분류 실험 정리

감귤 병해 **5클래스** 2D 이미지 분류를 위해 `[Tangerine_2D_AI/](../Tangerine_2D_AI/)`에 두었습니다. Colab에서 노트북 `train_tangerine_2d.ipynb`로 실행하는 흐름이며, 상세 실행·zip 업로드는 해당 폴더의 `[README.md](../Tangerine_2D_AI/README.md)`를 본다.

---

## 1. 데이터와 분할

- **입력**: `Tangerine_2D/` 아래 **클래스명 = 하위 폴더** (예: `Black spot`, `Canker`, `Greening`, `healthy`, `Scab`).
- **분할**: sklearn `train_test_split`으로 **계층화(stratified)** 해서 **train / validation / test** (기본 **70% / 15% / 15%**). 클래스 비율이 세 집합에 비슷하게 가도록 한다.

### Q. stratify로 왜 **두 번** 나누나?

**한 번에 세 덩어리**를 만들려는 목적이다. sklearn에는 “한 번에 70·15·15” 전용 API가 없어서, 관행적으로 다음처럼 **두 단계**로 나눈다.

1. 전체 → **test(15%)** vs **나머지(85%)** — `stratify`로 클래스 비율 유지
2. 나머지 85% 안에서 → **train** vs **val** — 전체 기준 val이 15%가 되도록 비율을 맞추고, 여기서도 `stratify`

구현상 “두 번”일 뿐, 의미는 **3-way stratified split**이다.

---

## 2. 모델(AI 설계) 요약

읽기 쉬운 한글 설명은 `[Tangerine_2D_AI/README.md`의 «모델 아키텍처»](../Tangerine_2D_AI/README.md#모델-아키텍처-한눈에) 절을 본다.


| 항목       | 내용                                                                 |
| -------- | ------------------------------------------------------------------ |
| 과제       | 다중 클래스 **단일 라벨** 이미지 분류                                            |
| 구조       | `torchvision` **ImageNet 사전학습** 백본 + 마지막 **분류 헤드만 클래스 수(5)** 로 교체  |
| 기본       | **ResNet-18**: `fc`를 `Linear(512 → K)` 로 교체, 입력은 보통 **224×RGB**    |
| 백본 옵션    | `resnet18`, `resnet50`, `efficientnet_b0` (`TrainConfig.backbone`) |
| Grad-CAM | ResNet은 `layer4`, EfficientNet은 `features[-1]`                     |


### Q. ResNet18을 쓴 거야, 50을 쓴 거야?

**노트북/설정에서 `backbone="resnet18"`(기본)** 이면 ResNet18이다. 학습 시작 시 PyTorch 허브에서 `resnet18-....pth` 를 받는 로그가 나오면 **18** 가중치를 쓴 것이다. `resnet50`이면 파일명에 `resnet50`이 보인다.

---

## 3. 손실·최적화·스케줄

### Q. 왜 CrossEntropy?

다중 클래스 분류에서 **정답이 클래스 하나**일 때의 표준 손실이다. 모델 출력은 softmax 이전 **로짓**에 대해 `nn.CrossEntropyLoss`를 쓰면, 내부에서 log-softmax + negative log-likelihood가 처리된다.

### Q. 왜 AdamW?

전이학습 실험에서 자주 쓰이는 옵티마이저이고, 가중치 감쇠를 그래디언트 업데이트와 **분리(decoupled)** 해 일반화에 유리한 경우가 많다. “유일한 정답”은 아니며, SGD+모멘텀 등 다른 선택도 가능하다.

### Q. “첫 시도” 기본값을 이렇게 잡은 이유

이미지 분류 + 전이학습에서 **문서·튜토리얼·실무에서 널리 쓰는 조합**을 베이스라인으로 둔 것이다. ResNet18은 상대적으로 가볍고, CrossEntropy + AdamW + 코사인 스케줄은 흔한 출발점이다. 데이터 규모·난이도에 따라 백본·학습률·에폭·증강은 조정하는 것이 맞다.

---

## 4. 전처리: Train vs Val/Test


| 구분             | 전처리                                         |
| -------------- | ------------------------------------------- |
| **Train**      | 랜덤 리사이즈 크롭, 수평 뒤집기, 약한 ColorJitter 등 **증강** |
| **Val / Test** | 고정 파이프라인: 리사이즈 → **센터 크롭**                  |
| **공통**         | ImageNet 평균·표준편차로 **정규화**                   |


### Q. 왜 이렇게 나눴나?

- **Train 증강**: 과적합 완화, 촬영 조건 변화에 대한 강건성을 기대하기 위한 일반적인 supervised 관행이다.
- **Val/Test 고정**: 평가할 때마다 입력이 달라지면(랜덤 크롭을 val에 쓰면) 같은 모델도 점수가 흔들리므로, **재현 가능한 동일 조건**으로 지표를 맞춘다.
- **ImageNet 통계**: 백본이 ImageNet으로 사전학습되어 있어 입력 분포를 맞추는 것이 수렴·성능에 유리하다.

---

## 5. 학습·검증·테스트 설계

한 **에폭(epoch)** 안에서 순서는 고정이다.

1. **Train**: train 이미지를 배치로 **한 번 전부** 순회하며 역전파로 가중치 갱신 (`train_one_epoch`, tqdm에 `train eN` 표시).
2. **Validation**: val 이미지를 **한 번 전부** 순회하며 **가중치는 고정**하고 loss·accuracy·**F1(macro/weighted/micro)** 를 계산 (`evaluate`, `val eN`).
3. 에폭이 끝난 뒤 `print`로 **한 줄 요약** (train/val loss·acc·**F1 macro**).
4. `**TrainConfig.best_metric`** 에 따라 `best.pt` 갱신: `val_accuracy`(기본) 또는 `**val_f1_macro**`(불균형·고 acc 의심 시 권장). 체크포인트에 `best_val_acc`, `best_val_f1_macro`가 함께 저장된다.

**Test** 집합은 **학습 루프에 쓰이지 않는다.** 노트북 기본 흐름은 `run_training(..., run_final_eval=False)`로 학습만 한 뒤, `**run_test_only(cfg)`** 를 별도 셀에서 실행해 `best.pt`로 **test** 평가·혼동 행렬·리포트(`test_classification_report.txt` 상단에 F1 요약)·**Grad-CAM**(테스트 로더 첫 배치 일부)을 만든다. 한 번에 돌리려면 `run_final_eval=True`를 쓸 수 있으나, 리포트 단계 오류 시 학습을 다시 하게 되기 쉬워 분리 실행을 권장한다.

선택 옵션 `freeze_backbone_epochs > 0`이면 초반 몇 에폭은 백본 고정·헤드만 학습한 뒤 전체를 푼다. 기본은 `0`이다.

---

## 6. 로그가 “언제” 보이나 (첫 에폭 요약이 늦게 뜨는 이유)

- **에폭 요약 한 줄** (`Epoch ... | train ... F1m ... | val ... F1m ...`)은 그 에폭에서 **train 전체 + val 전체**가 **끝난 뒤**에만 `print`된다.
- 그 전에는 `**train e1:` tqdm**만 갱신된다. 배치 수가 많거나 스텝이 느리면, 첫 요약 줄이 나오기까지 시간이 걸린다. 이는 **설계상 정상 동작**이다.
- **TensorBoard** 스칼라도 같은 에폭 구간에 기록되며, 그래프는 `%tensorboard --logdir ...`로 별도 실행해야 한다.

---

## 7. Colab에서 학습 셀이 돌아가는 동안 다른 확인

- **같은 노트북에서 다른 셀을 실행**하면, 보통 **이미 돌아가는 셀이 끝날 때까지 다음 실행이 대기**한다(실행이 “멈추는” 것이 아니라 **순서 대기**).  
- **실행 중인 셀을 멈추려면** 정지(■) 버튼으로 **인터럽트**해야 하며, 그때는 학습이 끊긴다.  
- 브라우저를 다른 탭으로만 옮기는 것은 **실행 중인 작업을 끊지 않는다.**

---

## 8. 산출물 위치 (요약)

기본 `output_dir / experiment_name` (예: `/content/Tangerine_2D_runs/tangerine_2d`)에 다음이 생긴다.

- `tensorboard/` — TensorBoard 로그  
- `best.pt`, `last.pt` — 체크포인트  
- `class_to_idx.json`, `splits.json` — 라벨·분할 기록  
- `test_classification_report.txt`, `test_confusion_matrix.png`  
- `gradcam/` — Grad-CAM 오버레이 이미지

---

## 9. 관련 파일


| 경로                                                                        | 역할                          |
| ------------------------------------------------------------------------- | --------------------------- |
| `[Tangerine_2D_AI/README.md](../Tangerine_2D_AI/README.md)`               | Colab zip·경로·기술 판단 요약       |
| `[Tangerine_2D_AI/config.py](../Tangerine_2D_AI/config.py)`               | `TrainConfig`               |
| `[Tangerine_2D_AI/data_loaders.py](../Tangerine_2D_AI/data_loaders.py)`   | 수집·stratified 분할·DataLoader |
| `[Tangerine_2D_AI/model_factory.py](../Tangerine_2D_AI/model_factory.py)` | 백본·헤드                       |
| `[Tangerine_2D_AI/experiment.py](../Tangerine_2D_AI/experiment.py)`       | 학습 루프·테스트·Grad-CAM 호출       |


