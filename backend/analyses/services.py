"""FastAPI 추론 서버 호출 — HTTP 요청·타임아웃·오류를 한 곳에서 처리"""
from __future__ import annotations

import requests
from django.conf import settings


class AIServiceError(Exception):
    """FastAPI 호출 실패 — 메시지는 사용자에게 보여 줄 문장"""


def predict_video(fileobj, filename: str) -> dict:
    url = f"{settings.AI_SERVICE_URL}/api/v1/predict/"
    try:
        r = requests.post(
            url,
            files={"file": (filename, fileobj, "application/octet-stream")},
            timeout=(5, settings.AI_SERVICE_TIMEOUT),        # (연결 5초, 응답 대기)
        )
    except requests.ConnectionError:
        raise AIServiceError(f"AI 서버에 연결할 수 없습니다 ({settings.AI_SERVICE_URL}).")
    except requests.Timeout:
        raise AIServiceError(f"AI 서버 응답 시간이 초과되었습니다 ({settings.AI_SERVICE_TIMEOUT}초).")

    if r.status_code == 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise AIServiceError(f"영상 분석 불가: {detail}")
    if r.status_code != 200:
        raise AIServiceError(f"AI 서버 오류 (HTTP {r.status_code})")
    return r.json()
