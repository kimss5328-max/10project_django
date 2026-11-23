from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    # 임시 메인 — 다음 단계에서 analyses 메인 화면으로 교체
    path("", login_required(TemplateView.as_view(template_name="home.html")), name="home"),
]