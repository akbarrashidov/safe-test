from django.urls import path

from .views import (
    ExamAnswerView,
    ExamFinishView,
    ExamQuestionView,
    ExamStartView,
    MyRequestsView,
    MyResultsView,
    PracticeBlockView,
    PracticeCheckView,
    RequestAccessView,
    TestListView,
)

urlpatterns = [
    path("tests/", TestListView.as_view(), name="test-list"),
    path("tests/<int:test_id>/request/", RequestAccessView.as_view(), name="test-request"),
    path("tests/my-requests/", MyRequestsView.as_view(), name="my-requests"),
    # Tayyorlanish rejimi
    path(
        "practice/<int:test_id>/block/<int:block>/",
        PracticeBlockView.as_view(),
        name="practice-block",
    ),
    path("practice/check/", PracticeCheckView.as_view(), name="practice-check"),
    # Imtihon rejimi
    path("exam/start/<int:test_id>/", ExamStartView.as_view(), name="exam-start"),
    path("exam/question/", ExamQuestionView.as_view(), name="exam-question"),
    path("exam/answer/", ExamAnswerView.as_view(), name="exam-answer"),
    path("exam/finish/", ExamFinishView.as_view(), name="exam-finish"),
    path("exam/my-results/", MyResultsView.as_view(), name="my-results"),
]
