"""
파이프라인 전역 설정 — 조절 가능한 값은 가능한 한 모두 여기에 둡니다.

- 기본값은 코드에 있으며, `configs/default_config.yaml` 또는 `--config 경로.yaml` 로 덮어쓸 수 있습니다.
- 키 목록 요약은 `CONFIG_KEYS.md` 를 참고하세요.

--------------------------------------------------------------------------------
데이터셋 폴더와의 관계 (프로젝트 루트 기준)
--------------------------------------------------------------------------------

1) `169.고품질 과수 작물 통합 데이터(이미지)\\01.데이터\\`
   - `1.Training\\라벨링데이터\\TL1.감귤\\` 아래에 부위·병해 별 하위 폴더가 있습니다.
     예: `열매_궤양병`, `잎_궤양병` 등 (잎/열매 등 촬영 부위 + 질병/해충 구분).
   - 각 샘플은 JSON 라벨 + 원천 이미지(JPEG 등)와 짝을 이룹니다.
   - JSON 안의 `Annotations.OBJECT_CLASS_CODE` 에 클래스 코드 문자열이 들어 있습니다.
     (예: `"감귤_궤양병"` — 데이터 사전에 정의된 코드).

2) `aihub_고품질 과수작물 통합 데이터_샘플\\`
   - 구조는 위와 유사하며, `라벨링데이터\\TL1.감귤\\...` 형태로 라벨 JSON이 있습니다.
   - 본 파이프라인의 `inference.class_names` 는 **학습에 쓰는 클래스 집합**이며,
     위 데이터의 `OBJECT_CLASS_CODE` 문자열과 **1:1로 맞출지, 영문/약어로 매핑할지**는
     학습 스크립트·데이터 전처리 단계에서 결정하면 됩니다.
   - `texture_pools` 등은 Blender에서 **질병별 텍스처 이미지 풀**을 가리킬 때,
     위 폴더의 `원천데이터` 경로나 클래스 폴더명과 연결할 수 있습니다.

--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # PyYAML 미설치 시 YAML 설정 사용 불가


# ---------------------------------------------------------------------------
# 설정 섹션 (사용자가 바꾸는 값은 전부 여기에 모읍니다)
# ---------------------------------------------------------------------------


@dataclass
class ExperimentConfig:
    """실험 식별자, 출력 루트, 로그 등 전역 옵션."""

    # 한 실험 묶음을 구분하는 ID. 출력 폴더명이 됩니다. (예: outputs/Exp_001/...)
    experiment_id: str = "Exp_001"
    # 렌더·증강·추론·보고서를 모두 담는 상위 디렉터리 (프로젝트 기준 상대 경로 권장)
    base_output_dir: str = "outputs"
    # 난수 시드 (Blender·2D 증강 등 재현성용; 완전 동일 재현은 JPEG 등에 한계 있음)
    seed: int = 42
    # Python 로깅 레벨: DEBUG, INFO, WARNING, ERROR
    log_level: str = "INFO"


@dataclass
class BlenderConfig:
    """
    Blender 헤드리스 시뮬레이션: 귤 스폰, 리지드 바디, 도메인 랜덤화, 렌더.

    텍스처·GT 질병 클래스는 `inference.class_names` 와 맞추는 것이 보고서 정확도 비교에 유리합니다.
    AI Hub / 169 데이터의 `OBJECT_CLASS_CODE` 와 이름을 통일하거나 매핑 테이블을 두세요.
    """

    # Blender 실행 파일 전체 경로. 비우면 시스템 PATH 의 `blender` / `blender.exe` 사용.
    blender_executable: str = ""
    # 메시·이미지 텍스처 등 에셋 루트 (기본 `data/Tangerine_3D`)
    assets_root: str = "data/Tangerine_3D"
    # 한 에피소드에서 생성할 귤 개수: 최소값 (무작위 범위의 하한)
    citrus_count_min: int = 2
    # 한 에피소드에서 생성할 귤 개수: 최대값 (무작위 범위의 상한)
    citrus_count_max: int = 5
    # 고정 개수만 쓰고 싶을 때 설정. None 이면 위 min~max 사이에서 균등 무작위.
    spawn_total: Optional[int] = None
    # 초당 스폰 개수 등 — 향후 스트리밍 스폰용 예약 필드 (현재는 0 권장)
    spawn_rate_per_sec: float = 0.0
    # 벨트(패시브 바디) 이동 속도 (Blender 단위/초). 애니메이션 및 모션 블러 강도 참고용.
    belt_speed: float = 1.0
    # 물리 엔진 품질: 서브스텝/반복에 영향 (값이 클수록 안정적이나 느려질 수 있음)
    physics_substeps: int = 10
    # 과일(액티브 리지드 바디) 마찰 계수 무작위 범위 — 구르기·미끄러짐 조절
    rigid_body_friction_min: float = 0.3
    rigid_body_friction_max: float = 0.8
    # 반발(튀는 정도). 컨베이어에서는 보통 낮게 유지.
    rigid_body_restitution: float = 0.1
    # 포인트 라이트 에너지(W) 무작위 범위 (밝기)
    light_energy_min: float = 50.0
    light_energy_max: float = 300.0
    # 조명 위치를 원점 기준 ±이 값(Blender 단위) 안에서 흔듦
    light_location_jitter: float = 2.0
    # 색온도(K) 범위 — 블랙바디 근사 등에 쓸 수 있음 (스크립트 구현에 따라 미사용일 수 있음)
    color_temperature_min: float = 4000.0
    color_temperature_max: float = 7000.0
    # 카메라 오일러 각도에 더하는 무작위 최대 각도(도)
    camera_jitter_deg: float = 5.0
    # 카메라 높이(Z 오프셋) 무작위 범위 — 낮은 값은 더 탑뷰에 가깝게
    camera_height_offset_min: float = 4.0
    camera_height_offset_max: float = 8.0
    # 스폰 시 귤 초기 회전 무작위 범위(도) — 다각도 노출 유도
    citrus_initial_rotation_jitter_deg: float = 180.0
    # 렌더 해상도 (픽셀)
    render_width: int = 640
    render_height: int = 480
    # 초당 프레임 수 (타임라인·물리 스텝과 함께 사용)
    render_fps: int = 24
    # 한 번의 실험에서 저장할 연속 프레임 수 (프레임 1 … N)
    episode_frame_count: int = 48
    # 질병(또는 정상) 클래스 이름 → 텍스처/머티리얼 ID 목록.
    # AI Hub·169 원천 이미지를 텍스처로 쓸 경우, 여기 값을 파일 경로나 폴더명으로 바꿀 수 있습니다.
    # 키는 `inference.class_names` 와 논리적으로 대응시키는 것이 좋습니다.
    texture_pools: dict = field(
        default_factory=lambda: {
            "Normal": ["default_orange"],
            "Canker": ["default_orange"],
            "Scab": ["default_orange"],
            "Black_spot": ["default_orange"],
        }
    )
    # 실험 출력 폴더 안에서 “원본 렌더 PNG 시퀀스”를 넣는 하위 폴더 이름
    renders_subdir: str = "renders"
    # 프레임·객체·GT 질병·(선택) 2D bbox 등 한 줄당 JSON — `src/blender_sim/metadata_schema.json` 참고
    metadata_filename: str = "frame_metadata.jsonl"


@dataclass
class PreprocessConfig:
    """
    Phase 1: 트리거·벨트 슬롯 인덱스 (시뮬/스텁; 추후 PLC·인코더는 동일 인터페이스로 교체).

    다중 카메라 오프셋은 `multi_camera_offsets` 에 픽셀 또는 슬롯 단위 보정값을 쌓아두고,
    `BeltSlotModel` 에서 합성하는 위치로 확장하면 됩니다.
    """

    # simulation: 프레임 동기 틱 + 이미지 x 기준 슬롯 / encoder_stub: 카운터만 증가 / passthrough: 슬롯 태깅 안 함
    mode: str = "simulation"
    # 논리적 이동 거리(예: mm) — 로그·메타용; 시뮬에선 슬롯 인덱스와 별개로 기록 가능
    mm_per_tick: float = 5.0
    # 이미지 가로를 균등 분할할 칸 수 (롤러 칸 인덱스)
    slots_count: int = 8
    # 시뮬에서 프레임마다 몇 틱 진행할지 (벨트 속도와의 스케일)
    tick_stride_frames: int = 1
    # 추론 단계에서 bbox 로 belt_slot_index 를 붙일지 (preprocess.mode 가 passthrough 이면 무시)
    attach_slots_during_inference: bool = True
    # 카메라별 슬롯 오프셋(정수, 슬롯 단위). 예: [0, 4] 는 추후 멀티 카메라 정렬용 예약
    multi_camera_offsets: List[int] = field(default_factory=list)
    # 선택: 슬롯 이벤트만 별도 파일로 남김
    write_slot_events_jsonl: bool = False
    slot_events_jsonl: str = "slot_events.jsonl"


@dataclass
class Augment2DConfig:
    """렌더 이미지에 대한 2D 후처리 (OpenCV). 순서는 `augment_order` 로 고정하는 것이 재현성에 유리합니다."""

    # 입력: 실험 출력 디렉터리 기준, 원본 렌더가 있는 하위 폴더 (보통 `renders`)
    input_subdir: str = "renders"
    # 출력: 증강된 PNG를 쓸 하위 폴더 (보통 `renders_aug` — 추론 단계 입력과 연결)
    output_subdir: str = "renders_aug"
    # 모션 블러 커널 최대 크기 (픽셀). 코드에서 홀수로 보정할 수 있음.
    motion_blur_max_kernel: int = 15
    # 각 프레임에 모션 블러를 적용할 확률 (0~1)
    motion_blur_probability: float = 0.6
    # True 이면 벨트 진행 방향에 맞춰 블러 방향을 쓰는 식으로 처리 (구현체 기준)
    blur_direction_tied_to_belt: bool = True
    # 이미지 평면에서 블러 방향(도). 0 은 수평 성분 위주 등 설정에 따름.
    belt_blur_angle_deg: float = 0.0
    # 가우시안 노이즈 표준편차 최소값 (픽셀 강도 스케일, OpenCV 기준)
    gaussian_noise_std_min: float = 0.0
    # 가우시안 노이즈 표준편차 최대값 — min~max 사이에서 균등 무작위
    gaussian_noise_std_max: float = 15.0
    # JPEG 저장 시 품질 하한 (1~100, 높을수록 고화질)
    jpeg_quality_min: int = 60
    # JPEG 저장 시 품질 상한 — min~max 사이에서 균등 무작위
    jpeg_quality_max: int = 95
    # 증강 연산 순서. 예: 모션블러 → 가우시안 → JPEG (문자열은 코드와 일치해야 함)
    augment_order: List[str] = field(
        default_factory=lambda: ["motion_blur", "gaussian_noise", "jpeg"]
    )


@dataclass
class InferenceConfig:
    """
    검출(YOLO detect) + 추적(ByteTrack 등) + 크롭 단위 질병 분류(softmax 전체).

    - 검출: "귤이 어디 있는지" 바운딩 박스.
    - 분류: 크롭마다 `class_names` 순서와 동일한 길이의 확률 벡터.
    - `classifier_weights` 가 비어 있으면 균일 분포로 대체하여 파이프라인만 통과시킵니다.

    학습 데이터는 `169.../TL1.감귤/...` 또는 `aihub.../TL1.감귤/...` 의 라벨 JSON·원천 이미지를 사용하면 되며,
    분류기 학습 시 클래스 순서는 반드시 아래 `class_names` 와 동일하게 맞추세요.
    """

    # Ultralytics 검출 가중치 (.pt). 귤 전용으로 학습한 모델 경로로 바꾸는 것이 좋습니다.
    detector_weights: str = "yolov8n.pt"
    # Ultralytics 분류 가중치 (.pt). 비우면 확률은 균일로 채움.
    classifier_weights: str = ""
    # 추론 디바이스: "cuda", "cpu", 또는 ""(자동 선택)
    device: str = ""
    # 설정 시 프로세스 시작 전 `CUDA_VISIBLE_DEVICES` 로 export (멀티 GPU 환경에서 유용)
    cuda_visible_devices: str = ""
    # 검출 신뢰도 임계값 — 낮추면 더 많은 박스, 노이즈 증가 가능
    conf_threshold: float = 0.25
    # NMS 등에 쓰는 IoU 임계값
    iou_threshold: float = 0.45
    # Ultralytics 트래커 설정 파일 이름 (패키지 내장 yaml, 예: bytetrack.yaml)
    tracker: str = "bytetrack.yaml"
    # 분류기 입력으로 리사이즈할 정사각형 한 변 길이(픽셀)
    cls_input_size: int = 224
    # 크롭 분류 시 배치 크기 — GPU 메모리에 맞게 조절
    batch_size_inference: int = 8
    # 최상위 질병 확률이 이 값 이상이면 경고(시각화·보고서에서 강조)로 취급
    alert_probability_threshold: float = 0.7
    # 집계 통계에서 "병해로 카운트"할 최소 확률 (보고서 disease_counts 등)
    stats_disease_threshold: float = 0.5
    # 질병·정상 클래스 이름 목록 (분류 모델 출력 차원과 순서 일치 필수).
    # 데이터셋의 `OBJECT_CLASS_CODE`(예: 감귤_궤양병)와 다른 이름을 쓰는 경우,
    # 학습 데이터 변환 단계에서 매핑하거나, 여기를 데이터 코드에 맞게 통일하세요.
    class_names: List[str] = field(
        default_factory=lambda: ["Normal", "Canker", "Scab", "Black_spot"]
    )
    # 추론 입력 이미지가 있는 하위 폴더 (보통 증강 결과인 `renders_aug`)
    inference_input_subdir: str = "renders_aug"
    # 프레임별 검출·추적·질병 확률을 한 줄씩 JSON 으로 저장하는 파일명
    predictions_jsonl: str = "predictions.jsonl"
    # --- 모듈형 백엔드 (미설정 시 기존 동작: two_stage + tracker 문자열 그대로)
    # yolo_unified | yolo_two_stage | mask_rcnn_torchvision
    detection_backend: str = "yolo_two_stage"
    # yolo_cls | mobilenet_v3 | none (unified/two_stage 에서 분류 경로 선택)
    classifier_backend: str = "yolo_cls"
    # 비어 있으면 `tracker` 키를 그대로 사용. botsort | bytetrack 이면 내장 yaml 로 매핑
    tracker_profile: str = ""
    # torchvision MobileNet 분류 헤드용 체크포인트(.pth 전체 state_dict 또는 호환 가중치)
    mobilenet_weights: str = ""
    # torchvision Mask R-CNN 백본 가중치: 비우면 COCO 사전학습 자동 다운로드
    mask_rcnn_weights: str = ""
    # Mask R-CNN 후 크롭 질병 분류를 끄려면 none (박스만)
    mask_rcnn_classify_crops: bool = True


@dataclass
class PostprocessConfig:
    """Phase 3: 논리 큐·배출 라우팅·드라이버 (비전과 하드웨어 분리)."""

    # top_disease 문자열 -> 라우트 id (예: Air 라인 / 리젝). "default" 키는 폴백
    routing_rules: Dict[str, str] = field(
        default_factory=lambda: {
            "Normal": "line_accept",
            "Canker": "line_reject",
            "Scab": "line_reject",
            "Black_spot": "line_reject",
            "default": "line_accept",
        }
    )
    # jsonl | print | noop
    driver: str = "jsonl"
    actuation_signals_jsonl: str = "actuation_signals.jsonl"
    # 동일 트랙에 대해 매 프레임 신호를 낼지, 라우트 변경 시에만 낼지
    emit_on_route_change_only: bool = True


@dataclass
class ReportConfig:
    """실험 출력 내 `reports/` 에 Markdown·HTML·크롭·차트를 생성합니다."""

    # 실험 출력 디렉터리 아래 보고서 루트 하위 폴더 이름
    reports_subdir: str = "reports"
    # True 이면 Jinja2 템플릿으로 `report.html` 생성 (jinja2 설치 필요)
    include_html: bool = True
    # 저장용 크롭 썸네일의 긴 변 최대값(픽셀) — 디스크·보고서 용량 절약
    crop_resize_max: int = 256
    # matplotlib 저장 시 DPI
    matplotlib_dpi: int = 120


@dataclass
class PipelineConfig:
    """위 섹션을 묶은 루트 설정. `main.py` 및 Blender 서브프로세스가 이 구조를 사용합니다."""

    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    blender: BlenderConfig = field(default_factory=BlenderConfig)
    augment: Augment2DConfig = field(default_factory=Augment2DConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    postprocess: PostprocessConfig = field(default_factory=PostprocessConfig)
    report: ReportConfig = field(default_factory=ReportConfig)

    @classmethod
    def from_dict(cls, data: dict) -> PipelineConfig:
        """중첩 dict(YAML/JSON)에서 로드. 알 수 없는 키는 무시합니다."""

        def _merge(section: Type[Any], overrides: dict) -> Any:
            base = asdict(section())
            names = {f.name for f in fields(section)}
            for k, v in (overrides or {}).items():
                if k in names:
                    base[k] = v
            return section(**base)

        exp = _merge(ExperimentConfig, data.get("experiment", {}))
        blend = _merge(BlenderConfig, data.get("blender", {}))
        aug = _merge(Augment2DConfig, data.get("augment", {}))
        pre = _merge(PreprocessConfig, data.get("preprocess", {}))
        inf = _merge(InferenceConfig, data.get("inference", {}))
        post = _merge(PostprocessConfig, data.get("postprocess", {}))
        rep = _merge(ReportConfig, data.get("report", {}))
        return cls(
            experiment=exp,
            blender=blend,
            augment=aug,
            preprocess=pre,
            inference=inf,
            postprocess=post,
            report=rep,
        )

    def to_dict(self) -> dict:
        """직렬화·로그 저장용."""
        return {
            "experiment": asdict(self.experiment),
            "blender": asdict(self.blender),
            "augment": asdict(self.augment),
            "preprocess": asdict(self.preprocess),
            "inference": asdict(self.inference),
            "postprocess": asdict(self.postprocess),
            "report": asdict(self.report),
        }

    def experiment_output_dir(self) -> Path:
        """현재 실험의 작업 디렉터리: `base_output_dir` / `experiment_id` (절대 경로)."""
        root = Path(self.experiment.base_output_dir) / self.experiment.experiment_id
        return root.resolve()

    def blender_config_path(self) -> Path:
        """Blender 서브프로세스에 넘기는 JSON 경로 (`dump_blender_job` 가 생성)."""
        return self.experiment_output_dir() / "blender_config.json"

    def reports_dir(self) -> Path:
        """보고서 루트: `base_output_dir` / `experiment_id` / `reports_subdir`"""
        return Path(self.experiment.base_output_dir) / self.experiment.experiment_id / self.report.reports_subdir


def load_pipeline_config(yaml_path: Optional[str] = None) -> PipelineConfig:
    """기본값 로드 후, YAML 이 있으면 병합. 경로 미지정 시 configs/default_config.yaml 우선."""
    cfg = PipelineConfig()
    root = Path(__file__).resolve().parent
    path: Optional[Path] = None
    if yaml_path:
        p = Path(yaml_path)
        if not p.is_absolute():
            p = root / p
        if p.is_file():
            path = p
    if path is None and yaml_path is None:
        for candidate in (root / "configs" / "default_config.yaml", root / "default_config.yaml"):
            if candidate.is_file():
                path = candidate
                break
    if path is not None:
        if yaml is None:
            raise RuntimeError("YAML 설정을 쓰려면: pip install pyyaml")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = PipelineConfig.from_dict(data)
    return cfg


def apply_cuda_env(cuda_visible_devices: str) -> None:
    """멀티 GPU 노드에서 특정 GPU만 쓰고 싶을 때 환경 변수 설정."""
    if cuda_visible_devices.strip():
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices.strip()


def write_json(path: Path, data: Any) -> None:
    """UTF-8 JSON 파일 쓰기 (디렉터리는 자동 생성)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def dump_blender_job(cfg: PipelineConfig) -> Path:
    """
    Blender 쪽에서 읽을 설정만 JSON 으로 저장합니다.

    `inference_class_names` 는 시뮬레이션 GT 질병 라벨 후보로 `inference.class_names` 를 전달합니다.
    """
    out = cfg.experiment_output_dir()
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": asdict(cfg.experiment),
        "blender": asdict(cfg.blender),
        "inference_class_names": list(cfg.inference.class_names),
    }
    path = cfg.blender_config_path()
    write_json(path, payload)
    return path
