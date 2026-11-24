"""
[2단계] 사람별 Sequence → Random Forest 예측 → Track ID·동작·신뢰도 정리
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .model_loader import ModelBundle
from .pose_pipeline import TrackData, track_to_sequence

BASE_DIR = Path(__file__).resolve().parents[1]
_rt = BASE_DIR / "configs" / "day07_realtime.json"
DEFAULT_THRESHOLD = json.loads(_rt.read_text(encoding="utf-8")).get("confidence_threshold", 0.55) if _rt.exists() else 0.55
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", DEFAULT_THRESHOLD))


def predict_tracks(bundle: ModelBundle, tracks: dict[int, TrackData]) -> tuple[list[dict], list[dict]]:
    """반환: (predictions, skipped) — 유효 Frame이 부족한 사람은 skipped"""
    rows, meta, skipped = [], [], []
    for tid in sorted(tracks):
        t = tracks[tid]
        if len(t.features) < bundle.min_valid_frames:
            skipped.append({"track_id": tid, "valid_frames": len(t.features),
                            "reason": f"유효 Frame {len(t.features)}개 < {bundle.min_valid_frames}"})
            continue
        x = track_to_sequence(t, bundle.sequence_steps)
        if x.shape[0] != bundle.feature_count or not np.all(np.isfinite(x)):
            skipped.append({"track_id": tid, "valid_frames": len(t.features), "reason": "Feature 생성 실패"})
            continue
        rows.append(x)
        meta.append((tid, t))

    if not rows:
        return [], skipped

    proba = bundle.model.predict_proba(np.stack(rows))
    classes = [str(c) for c in bundle.model.classes_]
    out = []
    for (tid, t), p in zip(meta, proba):
        i = int(np.argmax(p))
        conf = float(p[i])
        out.append({
            "track_id": int(tid),
            "action_label": classes[i],
            "confidence": round(conf, 4),
            "uncertain": conf < CONFIDENCE_THRESHOLD,
            "valid_frames": len(t.features),
            "first_frame": int(t.frame_ids[0]),
            "last_frame": int(t.frame_ids[-1]),
            "probabilities": {c: round(float(v), 4) for c, v in zip(classes, p)},
        })
    return out, skipped
