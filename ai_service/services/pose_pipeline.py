"""
[2단계] 영상 → 사람(Track ID)별 30-Step Sequence

처리 순서 (학습·8일차 다중 인물 코드와 같은 계산)
  1. YOLO11 Pose + ByteTrack(persist=True) 로 사람 박스와 Track ID
  2. 각 박스 안을 MediaPipe Pose heavy 로 다시 추출 → COCO 17점 (src.heavy_pose.HeavyTrackYOLO)
  3. Frame마다 38-D Feature = 어깨폭 정규화 좌표 34 + 팔꿈치·무릎 각도 4 (학습 frame_feature_from_row 와 동일)
  4. Track ID별로 유효 Frame을 모아 frame_id 기준 30 Step 으로 다시 맞춤 → 1,140 Feature
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from src.feature_utils import normalize_by_shoulder_width, selected_joint_angles
from src.heavy_pose import HeavyTrackYOLO
from src.sequence_utils import flatten_sequence, resample_sequence

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
if not MODEL_DIR.is_absolute():
    MODEL_DIR = BASE_DIR / MODEL_DIR

PROJECT = json.loads((BASE_DIR / "project.json").read_text(encoding="utf-8"))
YOLO_WEIGHTS = MODEL_DIR / PROJECT.get("pose_model", "yolo11n-pose.pt")
HEAVY_WEIGHTS = MODEL_DIR / "pose_landmarker_heavy.task"
PERSON_CONF = float(PROJECT.get("person_confidence", 0.25))
TRACKER = os.getenv("TRACKER", "bytetrack.yaml")
MAX_VIDEO_SECONDS = float(os.getenv("MAX_VIDEO_SECONDS", "60"))     # 너무 긴 영상은 앞부분만

_lock = threading.Lock()            # YOLO·MediaPipe 객체는 동시에 여러 요청이 쓰면 안 됨


class VideoReadError(Exception):
    """영상 파일을 열 수 없거나 Frame이 없음 → 400"""


@dataclass
class TrackData:
    features: list = field(default_factory=list)
    frame_ids: list = field(default_factory=list)


def feature_from_keypoints(kp: np.ndarray) -> np.ndarray | None:
    """COCO 17점 (17,2) → 학습과 같은 38-D Feature. 계산 불가면 None"""
    if kp.shape != (17, 2) or not np.all(np.isfinite(kp)):
        return None
    try:
        norm, _, _ = normalize_by_shoulder_width(kp)
    except ValueError:
        return None
    ang = selected_joint_angles(kp)
    feat = [float(v) for pt in norm for v in pt[:2]]
    feat += [float(ang[k]) for k in ("left_elbow_angle", "right_elbow_angle", "left_knee_angle", "right_knee_angle")]
    feat = np.asarray(feat, dtype=np.float32)
    return feat if len(feat) == 38 and np.all(np.isfinite(feat)) else None


def check_weights() -> dict:
    return {"yolo": YOLO_WEIGHTS.exists(), "heavy": HEAVY_WEIGHTS.exists()}


def extract_tracks(video_path: str | Path) -> dict:
    """영상 1개 → {'video': 메타정보, 'tracks': {track_id: TrackData}, 'pose': 처리 통계}"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VideoReadError("영상 파일을 열 수 없습니다.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    max_frames = int(MAX_VIDEO_SECONDS * fps)

    tracks: dict[int, TrackData] = {}
    read = person_frames = 0
    with _lock:
        model = HeavyTrackYOLO(str(YOLO_WEIGHTS), model_path=HEAVY_WEIGHTS)   # 요청마다 새로 → Track ID가 1부터 시작
        try:
            while read < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                fid = read
                read += 1
                result = model.track(frame, persist=True, tracker=TRACKER, conf=PERSON_CONF, verbose=False)[0]
                if result.boxes is None or result.boxes.id is None or len(result.boxes) == 0:
                    continue
                person_frames += 1
                ids = result.boxes.id.int().cpu().tolist()
                kps = result.keypoints.xy.cpu().numpy()
                for tid, kp in zip(ids, kps):
                    feat = feature_from_keypoints(np.asarray(kp, dtype=np.float32))
                    if feat is None:
                        continue
                    t = tracks.setdefault(int(tid), TrackData())
                    t.features.append(feat)
                    t.frame_ids.append(fid)
            heavy, fallback = model.heavy_count, model.fallback_count
        finally:
            cap.release()
            try:
                model._lm.close()
            except Exception:
                pass

    if read == 0:
        raise VideoReadError("영상에서 Frame을 읽지 못했습니다(손상되었거나 지원하지 않는 형식).")
    return {
        "video": {"frames": read, "total_frames": total, "fps": round(float(fps), 2),
                  "duration_sec": round(read / fps, 2), "truncated": total > read},
        "tracks": tracks,
        "pose": {"person_frames": person_frames, "heavy_count": heavy, "fallback_count": fallback},
    }


def track_to_sequence(track: TrackData, steps: int) -> np.ndarray:
    """한 사람의 유효 Frame들 → (steps×38,) 1차원 입력"""
    seq = resample_sequence(np.stack(track.features), np.asarray(track.frame_ids), target_steps=steps)
    return flatten_sequence(seq)
