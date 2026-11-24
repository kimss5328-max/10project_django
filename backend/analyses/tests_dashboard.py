"""[10단계] 대시보드 권한·집계 테스트"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from .models import AnalysisJob


@patch("analyses.page_views._model_info", return_value={"ok": True, "classes": ["a", "b", "c"], "version": "x"})
class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("normal", password="Vision#2026")
        self.staff = User.objects.create_user("boss", password="Vision#2026", is_staff=True)
        j1 = AnalysisJob.objects.create(user=self.user, input_type="UPLOAD", status="COMPLETED")
        j1.predictions.create(track_id=1, action_label="a", confidence=0.9)
        j1.predictions.create(track_id=2, action_label="a", confidence=0.7)
        AnalysisJob.objects.create(user=self.user, input_type="CAMERA", status="FAILED")

    def test_anonymous_redirect(self, _):
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)

    def test_normal_user_forbidden(self, _):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/").status_code, 403)

    def test_staff_sees_real_counts(self, _):
        self.client.force_login(self.staff)
        r = self.client.get("/dashboard/")
        self.assertEqual(r.status_code, 200)
        d = r.context["chart_data"]
        self.assertEqual(dict(zip(d["actions"]["labels"], d["actions"]["counts"])), {"a": 2, "b": 0, "c": 0})
        self.assertEqual(dict(zip(d["statuses"]["keys"], d["statuses"]["counts"])),
                         {"PENDING": 0, "PROCESSING": 0, "COMPLETED": 1, "FAILED": 1})
        self.assertEqual(r.context["totals"]["jobs"], 2)
