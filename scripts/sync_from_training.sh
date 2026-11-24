#!/usr/bin/env bash
# 학습 프로젝트 산출물을 ai_service로 가져온다.
# 사용: bash scripts/sync_from_training.sh [학습프로젝트] [artifacts 하위폴더: day06 | team]
set -euo pipefail
SRC_ROOT="${1:-$HOME/ai_vision/mothion}"
ART="${2:-team}"
A="$SRC_ROOT/artifacts/$ART"
DST="$(cd "$(dirname "$0")/.." && pwd)/ai_service"
echo "[원본] $A"
mkdir -p "$DST/models" "$DST/src" "$DST/configs"

# 1) 모델 3개 (joblib 이름은 ai_service 안에서 rf_action_baseline.joblib 로 통일)
JOBLIB=$(ls "$A"/rf_action_*.joblib | head -1)
cp -v "$JOBLIB" "$DST/models/rf_action_baseline.joblib"
cp -v "$A/rf_feature_columns.json" "$A/rf_training_info.json" "$DST/models/"

# 2) 추론 유틸 (+ heavy 어댑터)
for f in pose_utils feature_utils sequence_utils realtime_utils multi_person_utils heavy_pose; do
  [ -f "$SRC_ROOT/src/$f.py" ] && cp -v "$SRC_ROOT/src/$f.py" "$DST/src/" || echo "  (없음) src/$f.py"
done
touch "$DST/src/__init__.py"

# 3) 설정 + YOLO 가중치(사람 박스·ByteTrack용)
cp -v "$SRC_ROOT/configs/project.json" "$DST/"
for c in action_classes.csv action_classes_heavy.csv day07_realtime.json day08_multi_person.json; do
  [ -f "$SRC_ROOT/configs/$c" ] && cp -v "$SRC_ROOT/configs/$c" "$DST/configs/"
done
PT=$(python3 -c "import json;print(json.load(open('$SRC_ROOT/configs/project.json'))['pose_model'])")
[ -f "$SRC_ROOT/$PT" ] && cp -v "$SRC_ROOT/$PT" "$DST/models/" || echo "  (없음) $PT — ultralytics가 자동 다운로드"

# 4) 기록
python3 - "$DST/models" "$A" "$(basename "$JOBLIB")" <<'PY'
import json, sys, datetime, hashlib, pathlib
m = pathlib.Path(sys.argv[1]); info = json.loads((m/"rf_training_info.json").read_text(encoding="utf-8"))
rec = {"synced_at": datetime.datetime.now().isoformat(timespec="seconds"), "source": sys.argv[2],
       "original_joblib": sys.argv[3],
       "joblib_md5": hashlib.md5((m/"rf_action_baseline.joblib").read_bytes()).hexdigest()[:10],
       "pose_model": info.get("pose_model", "yolo"), "classes": info.get("classes"),
       "feature_count": info.get("feature_count"), "sequence_steps": info.get("sequence_steps")}
(m/"MODEL_VERSION.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(rec, ensure_ascii=False, indent=2))
PY
