"""T01: 모델·Feature·학습정보를 불러와 입력 규격을 확인"""
import json
from pathlib import Path
import joblib

M = Path(__file__).resolve().parent / "models"
model = joblib.load(M / "rf_action_baseline.joblib")
cols = json.loads((M / "rf_feature_columns.json").read_text(encoding="utf-8"))
info = json.loads((M / "rf_training_info.json").read_text(encoding="utf-8"))

print("classes        :", list(model.classes_))
print("model 입력 수   :", model.n_features_in_)
print("feature 목록 수 :", len(cols))
print("sequence_steps :", info["sequence_steps"], "| feature_count:", info.get("feature_count"))
assert model.n_features_in_ == len(cols) == info["sequence_steps"] * 38, "입력 차원 불일치"
assert set(map(str, model.classes_)) == set(map(str, info["classes"])), "Class 불일치"
print("T01 PASS")

import src.realtime_utils, src.multi_person_utils, src.sequence_utils, src.feature_utils  # noqa
print("src import OK")
