"""analyses 앱 URL — DRF API + 사용자 화면 (10단계에서 /dashboard/ 추가)"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import page_views
from .views import AnalysisJobViewSet

router = DefaultRouter()
router.register("analyses", AnalysisJobViewSet, basename="analysis")

urlpatterns = [
    path("api/v1/", include(router.urls)),
    path("api/v1/cameras/<str:name>/stream/", page_views.camera_stream, name="camera_stream"),
    path("analyses/", page_views.analysis_page, name="analysis_page"),
]
