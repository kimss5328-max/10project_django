"""
[2단계] 학습 산출물 로드와 입력 규격 검사

- 서버가 시작될 때 한 번만 joblib·JSON을 읽고(load_model_bundle), 이후 요청은 get_bundle()로 재사용
- 검사: 모델 입력 수 == Feature 목록 수 == sequence_steps × 38,
        Feature 이름·순서 == 학습 코드(sequence_feature_names)와 동일,
        model.classes_ == rf_training_info.json 의 classes
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import joblib

from src.sequence_utils import sequence_feature_names

BASE_DIR = Path(__file__).resolve().parents[1]            # ai_service/
MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
if not MODEL_DIR.is_absolute():
    MODEL_DIR = BASE_DIR / MODEL_DIR

FRAME_FEATURES = 38                                       # 정규화 좌표 34 + 관절각도 4


@dataclass
class ModelBundle:
    model: object
    feature_columns: list[str]
    info: dict
    classes: list[str]
    sequence_steps: int
    feature_count: int
    min_valid_frames: int
    version: dict = field(default_factory=dict)


_bundle: ModelBundle | None = None


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_model_bundle() -> ModelBundle:
    global _bundle
    model = joblib.load(MODEL_DIR / "rf_action_baseline.joblib")    # 본인 팀이 만든 신뢰 가능한 파일만 로드
    columns = _read_json(MODEL_DIR / "rf_feature_columns.json")
    info = _read_json(MODEL_DIR / "rf_training_info.json")
    version_path = MODEL_DIR / "MODEL_VERSION.json"
    version = _read_json(version_path) if version_path.exists() else {}

    steps = int(info["sequence_steps"])
    expected = steps * FRAME_FEATURES
    if not (model.n_features_in_ == len(columns) == int(info["feature_count"]) == expected):
        raise RuntimeError(
            f"입력 차원 불일치: model={model.n_features_in_}, columns={len(columns)}, "
            f"info={info['feature_count']}, steps×38={expected}")
    if list(columns) != sequence_feature_names(steps):
        raise RuntimeError("rf_feature_columns.json 순서가 학습 코드의 Feature 순서와 다릅니다.")
    classes = [str(c) for c in model.classes_]
    if set(classes) != set(map(str, info["classes"])):
        raise RuntimeError(f"Class 불일치: model={classes}, info={info['classes']}")

    _bundle = ModelBundle(model=model, feature_columns=list(columns), info=info, classes=classes,
                          sequence_steps=steps, feature_count=expected,
                          min_valid_frames=int(info.get("min_valid_frames", 10)), version=version)
    return _bundle


def get_bundle() -> ModelBundle:
    if _bundle is None:
        raise RuntimeError("모델이 아직 로드되지 않았습니다.")
    return _bundle


def is_ready() -> bool:
    return _bundle is not None
