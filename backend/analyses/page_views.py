"""
[9단계] 사용자 HTML 화면 + 카메라 미리보기
- analysis_page : /analyses/  업로드·IP Webcam 선택, 분석 시작, 상태·결과·최근 이력 (데이터는 JS가 DRF API로 조회)
- camera_stream : /api/v1/cameras/<이름>/stream/  허용된 카메라의 MJPEG을 Django가 대신 전달
                  → 브라우저에는 카메라 실제 주소가 노출되지 않음, 로그인 사용자만
"""
from __future__ import annotations

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def _model_info() -> dict:
    """FastAPI /health 에서 현재 모델 정보(동작 목록)를 가져옴. 실패해도 화면은 뜨게."""
    try:
        d = requests.get(f"{settings.AI_SERVICE_URL}/health", timeout=2).json()
        return {"ok": d.get("status") == "ok", "classes": d.get("classes", []),
                "version": (d.get("model_version") or {}).get("joblib_md5", "")}
    except Exception:
        return {"ok": False, "classes": [], "version": ""}


@login_required
def analysis_page(request):
    return render(request, "analyses/index.html", {
        "cameras": list(settings.ALLOWED_CAMERAS),          # 이름만 전달 (주소 X)
        "capture_seconds": settings.CAMERA_CAPTURE_SECONDS,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "model": _model_info(),
    })


@login_required
@require_GET
def camera_stream(request, name: str):
    url = settings.ALLOWED_CAMERAS.get(name)
    if not url:
        raise Http404("허용되지 않은 카메라")
    try:
        upstream = requests.get(url, stream=True, timeout=(5, 10))
    except requests.RequestException:
        return HttpResponse("카메라에 연결할 수 없습니다.", status=502)
    if upstream.status_code != 200:
        upstream.close()
        return HttpResponse(f"카메라 응답 오류 ({upstream.status_code})", status=502)

    def relay():
        try:
            for chunk in upstream.iter_content(chunk_size=16384):
                if chunk:
                    yield chunk
        finally:
            upstream.close()        # 브라우저가 미리보기를 끄면 카메라 연결도 닫음

    resp = StreamingHttpResponse(relay(), content_type=upstream.headers.get(
        "Content-Type", "multipart/x-mixed-replace; boundary=--BoundaryString"))
    resp["Cache-Control"] = "no-store"
    return resp
