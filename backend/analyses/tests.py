from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import AnalysisJob

URL = "/api/v1/analyses/"


def fake_mp4(name="clip.mp4"):
    return SimpleUploadedFile(name, b"\x00\x00\x00\x18ftypmp42" + b"0" * 1000, content_type="video/mp4")


@override_settings(MEDIA_ROOT="/tmp/vap_test_media")
class AnalysisApiTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("user_a", password="Vision#2026")
        self.b = User.objects.create_user("user_b", password="Vision#2026")
        self.admin = User.objects.create_user("boss", password="Vision#2026", is_staff=True)
        self.c = APIClient()

    def create_job(self, user):
        self.c.force_authenticate(user)
        r = self.c.post(URL, {"input_type": "UPLOAD", "video": fake_mp4(), "title": "t"}, format="multipart")
        self.c.force_authenticate(None)
        return r

    # 1. 비로그인 거부
    def test_01_anonymous_forbidden(self):
        self.assertIn(self.c.get(URL).status_code, (401, 403))

    # 2. 로그인 → 빈 목록
    def test_02_empty_list(self):
        self.c.force_authenticate(self.a)
        self.assertEqual(self.c.get(URL).json(), [])

    # 3. 업로드 생성 → 201, PENDING, DB 저장
    def test_03_create_pending(self):
        r = self.create_job(self.a)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["status"], "PENDING")
        self.assertEqual(AnalysisJob.objects.get(pk=r.json()["id"]).user, self.a)

    # 4. 잘못된 입력: 영상 없음 / txt
    def test_04_invalid_upload(self):
        self.c.force_authenticate(self.a)
        r1 = self.c.post(URL, {"input_type": "UPLOAD"}, format="multipart")
        r2 = self.c.post(URL, {"input_type": "UPLOAD", "video": SimpleUploadedFile("a.txt", b"hello")}, format="multipart")
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r2.status_code, 400)
        self.assertIn("video", r2.json())

    # 5. 허용되지 않은 카메라
    def test_05_camera_not_allowed(self):
        self.c.force_authenticate(self.a)
        r = self.c.post(URL, {"input_type": "CAMERA", "camera_name": "phone1"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("camera_name", r.json())

    # 6. 상세·상태 조회
    def test_06_detail_and_status(self):
        jid = self.create_job(self.a).json()["id"]
        self.c.force_authenticate(self.a)
        self.assertEqual(self.c.get(f"{URL}{jid}/").status_code, 200)
        s = self.c.get(f"{URL}{jid}/status/").json()
        self.assertEqual((s["status"], s["done"]), ("PENDING", False))

    # 7. PATCH: 제목만 바뀌고 status는 그대로
    def test_07_patch_only_title(self):
        jid = self.create_job(self.a).json()["id"]
        self.c.force_authenticate(self.a)
        r = self.c.patch(f"{URL}{jid}/", {"title": "새 제목", "status": "COMPLETED"}, format="json")
        self.assertEqual(r.status_code, 200)
        job = AnalysisJob.objects.get(pk=jid)
        self.assertEqual((job.title, job.status), ("새 제목", "PENDING"))

    # 8. 다른 사용자: 조회·수정·삭제 모두 404
    def test_08_other_user_blocked(self):
        jid = self.create_job(self.a).json()["id"]
        self.c.force_authenticate(self.b)
        self.assertEqual(self.c.get(f"{URL}{jid}/").status_code, 404)
        self.assertEqual(self.c.patch(f"{URL}{jid}/", {"title": "x"}, format="json").status_code, 404)
        self.assertEqual(self.c.delete(f"{URL}{jid}/").status_code, 404)
        self.assertEqual(self.c.get(URL).json(), [])

    # 9. 관리자는 전체 조회
    def test_09_admin_sees_all(self):
        self.create_job(self.a)
        self.create_job(self.b)
        self.c.force_authenticate(self.admin)
        self.assertEqual(len(self.c.get(URL).json()), 2)

    # (추가) 본인 삭제 → 예측까지 함께 삭제
    def test_10_owner_delete(self):
        jid = self.create_job(self.a).json()["id"]
        AnalysisJob.objects.get(pk=jid).predictions.create(track_id=1, action_label="wave", confidence=0.8)
        self.c.force_authenticate(self.a)
        self.assertEqual(self.c.delete(f"{URL}{jid}/").status_code, 204)
        self.assertFalse(AnalysisJob.objects.filter(pk=jid).exists())
