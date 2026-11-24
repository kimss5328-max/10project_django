from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django.db import transaction
from .tasks import run_analysis


from .models import AnalysisJob
from .serializers import AnalysisJobSerializer, AnalysisJobUpdateSerializer


class AnalysisJobViewSet(viewsets.ModelViewSet):
    """
    POST   /api/v1/analyses/              작업 생성 → PENDING
    GET    /api/v1/analyses/              내 작업 목록 (관리자는 전체)
    GET    /api/v1/analyses/{id}/         상세 + 사람별 결과
    PATCH  /api/v1/analyses/{id}/         제목·메모만 수정
    DELETE /api/v1/analyses/{id}/         삭제 (사람별 예측도 함께 삭제)
    GET    /api/v1/analyses/{id}/status/  상태만 가볍게 조회
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]   # PUT 전체 수정 금지

    def get_queryset(self):
        qs = AnalysisJob.objects.select_related("user").prefetch_related("predictions")
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)      # 남의 작업은 404

    def get_serializer_class(self):
        if self.action == "partial_update":
            return AnalysisJobUpdateSerializer
        return AnalysisJobSerializer

    def perform_create(self, serializer):
        job = serializer.save(user=self.request.user, status=AnalysisJob.Status.PENDING)

        def enqueue():
            result = run_analysis.delay(job.id)
            AnalysisJob.objects.filter(pk=job.id).update(celery_task_id=result.id)

        # DB 저장(커밋)이 끝난 뒤에 등록 → Worker가 아직 없는 Job을 찾는 문제 방지
        transaction.on_commit(enqueue)

    def perform_destroy(self, instance):
        if instance.video:
            instance.video.delete(save=False)            # 업로드 파일도 정리
        instance.delete()

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        job = self.get_object()
        return Response({
            "id": job.id, "status": job.status, "status_display": job.get_status_display(),
            "done": job.status in (AnalysisJob.Status.COMPLETED, AnalysisJob.Status.FAILED),
            "result_message": job.result_message, "error_message": job.error_message,
            "prediction_count": job.predictions.count(),
        })
