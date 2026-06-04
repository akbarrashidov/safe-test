from rest_framework import serializers

from .models import Question, Test, TestAccessRequest


class TestListSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)
    block_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Test
        fields = [
            "id", "title", "description",
            "time_limit_min", "exam_question_count",
            "block_size", "block_count", "question_count",
        ]


class AccessRequestSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source="test.title", read_only=True)

    class Meta:
        model = TestAccessRequest
        fields = ["id", "test", "test_title", "status", "comment", "created_at", "reviewed_at"]
        read_only_fields = ["status", "created_at", "reviewed_at"]


class QuestionPublicSerializer(serializers.ModelSerializer):
    """API uchun savol — `correct_index` ATAYIN yo'q."""

    class Meta:
        model = Question
        fields = ["id", "order", "text", "options"]
