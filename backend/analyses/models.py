from django.conf import settings
from django.db import models


class AnalysisJob(models.Model):
    """사용자 한 번의 'AI 분석 시작' 요청 = 작업 1건"""

    class Status(models.TextChoices):
        PENDING = "PENDING", "대기"
        PROCESSING = "PROCESSING", "처리 중"
        COMPLETED = "COMPLETED", "완료"
        FAILED = "FAILED", "실패"

    class InputType(models.TextChoices):
        UPLOAD = "UPLOAD", "영상 업로드"
        CAMERA = "CAMERA", "IP Webcam"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="analysis_jobs")
    title = models.CharField("제목", max_length=100, blank=True)
    memo = models.TextField("메모", blank=True)

    input_type = models.CharField("입력 방식", max_length=10, choices=InputType.choices)
    video = models.FileField("영상 파일", upload_to="analyses/%Y/%m/%d/", blank=True)
    camera_name = models.CharField("카메라 이름", max_length=50, blank=True)
    expected_action = models.CharField("수행하려는 동작(참고용)", max_length=50, blank=True)

    status = models.CharField("상태", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    celery_task_id = models.CharField(max_length=64, blank=True)
    error_message = models.TextField("오류 내용", blank=True)
    result_message = models.CharField("결과 안내", max_length=200, blank=True)
    model_version = models.CharField("모델 버전", max_length=32, blank=True)
    processing_sec = models.FloatField("처리 시간(초)", null=True, blank=True)

    created_at = models.DateTimeField("생성 시각", auto_now_add=True)
    started_at = models.DateTimeField("시작 시각", null=True, blank=True)
    completed_at = models.DateTimeField("종료 시각", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "분석 작업"
        verbose_name_plural = "분석 작업"

    def __str__(self):
        return f"#{self.pk} {self.user} {self.get_input_type_display()} {self.status}"


class PersonPrediction(models.Model):
    """작업 1건 안에서 추적된 사람 1명의 예측 결과"""

    job = models.ForeignKey(AnalysisJob, on_delete=models.CASCADE, related_name="predictions")
    track_id = models.PositiveIntegerField("Track ID")
    action_label = models.CharField("예측 동작", max_length=50)
    confidence = models.FloatField("신뢰도")
    uncertain = models.BooleanField("판단 불확실", default=False)
    valid_frames = models.PositiveIntegerField("유효 Frame 수", default=0)
    first_frame = models.PositiveIntegerField(null=True, blank=True)
    last_frame = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["job", "track_id"]
        constraints = [models.UniqueConstraint(fields=["job", "track_id"], name="uniq_job_track")]
        verbose_name = "사람별 예측"
        verbose_name_plural = "사람별 예측"

    def __str__(self):
        return f"Job#{self.job_id} Track{self.track_id} {self.action_label} ({self.confidence:.2f})"
