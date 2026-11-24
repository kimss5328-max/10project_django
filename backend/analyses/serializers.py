from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .models import AnalysisJob, PersonPrediction

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi"}


class PersonPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonPrediction
        fields = ("track_id", "action_label", "confidence", "uncertain", "valid_frames", "first_frame", "last_frame")
        read_only_fields = fields


class AnalysisJobSerializer(serializers.ModelSerializer):
    """생성·조회용. 상태·결과 필드는 서버만 바꿀 수 있음(read_only)"""
    predictions = PersonPredictionSerializer(many=True, read_only=True)
    user = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AnalysisJob
        fields = ("id", "user", "title", "memo", "input_type", "video", "camera_name", "expected_action",
                  "status", "result_message", "error_message", "model_version", "processing_sec",
                  "created_at", "started_at", "completed_at", "predictions")
        read_only_fields = ("status", "result_message", "error_message", "model_version", "processing_sec",
                            "created_at", "started_at", "completed_at")

    def validate(self, attrs):
        input_type = attrs.get("input_type")
        video = attrs.get("video")
        camera = attrs.get("camera_name", "")

        if input_type == AnalysisJob.InputType.UPLOAD:
            if not video:
                raise serializers.ValidationError({"video": "영상 파일을 선택하세요."})
            if Path(video.name).suffix.lower() not in ALLOWED_VIDEO_EXT:
                raise serializers.ValidationError({"video": f"지원 형식: {', '.join(sorted(ALLOWED_VIDEO_EXT))}"})
            if video.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                raise serializers.ValidationError({"video": f"{settings.MAX_UPLOAD_MB}MB 이하만 업로드할 수 있습니다."})
            attrs["camera_name"] = ""
        elif input_type == AnalysisJob.InputType.CAMERA:
            if video:
                raise serializers.ValidationError({"video": "IP Webcam 방식에서는 파일을 보내지 않습니다."})
            if camera not in settings.ALLOWED_CAMERAS:
                raise serializers.ValidationError({"camera_name": "허용된 카메라가 아닙니다."})
        return attrs


class AnalysisJobUpdateSerializer(serializers.ModelSerializer):
    """PATCH 전용 — 제목·메모만 수정 가능"""
    class Meta:
        model = AnalysisJob
        fields = ("title", "memo")
