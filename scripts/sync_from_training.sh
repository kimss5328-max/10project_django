#!/usr/bin/env bash
# 학습 프로젝트(subject10_pose_action)의 결과물을 ai_service로 다시 가져온다.
# 사용: bash scripts/sync_from_training.sh [학습프로젝트 경로] [artifacts 하위폴더]
set -euo pipefail
SRC_ROOT="${1:-$HOME/ai_vision/subject10_pose_action}"
ART="${2:-day06}"
DST="$(cd "$(dirname "$0")/.." && pwd)/ai_service"

echo "[원본] $SRC_ROOT  (artifacts/$ART)"
mkdir -p "$DST/models" "$DST/src"

# 1) 모델 3개 파일
for f in rf_action_baseline.joblib rf_feature_columns.json rf_training_info.json; do
  cp -v "$SRC_ROOT/artifacts/$ART/$f" "$DST/models/"
done

# 2) 추론 유틸 (있는 것만)
for f in pose_utils feature_utils sequence_utils realtime_utils multi_person_utils; do
  if [ -f "$SRC_ROOT/src/$f.py" ]; then cp -v "$SRC_ROOT/src/$f.py" "$DST/src/"; else echo "  (없음, 건너뜀) src/$f.py"; fi
done
touch "$DST/src/__init__.py"

# 3) Pose 설정 + YOLO 가중치
cp -v "$SRC_ROOT/configs/project.json" "$DST/"
PT=$(python3 -c "import json;print(json.load(open('$SRC_ROOT/configs/project.json'))['pose_model'])"); cp -v "$SRC_ROOT/$PT" "$DST/models/"

# 4) 어떤 모델을 가져왔는지 기록
python3 - "$DST/models" "$SRC_ROOT" "$ART" <<'PY'
import json, sys, datetime, hashlib, pathlib
m = pathlib.Path(sys.argv[1]); info = json.loads((m/"rf_training_info.json").read_text(encoding="utf-8"))
h = hashlib.md5((m/"rf_action_baseline.joblib").read_bytes()).hexdigest()[:10]
rec = {"synced_at": datetime.datetime.now().isoformat(timespec="seconds"),
       "source": f"{sys.argv[2]}/artifacts/{sys.argv[3]}", "joblib_md5": h,
       "classes": info.get("classes"), "feature_count": info.get("feature_count", info.get("n_features")),
       "sequence_steps": info.get("sequence_steps")}
(m/"MODEL_VERSION.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(rec, ensure_ascii=False, indent=2))
PY
echo "완료 → $DST"
