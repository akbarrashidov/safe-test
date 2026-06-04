"""
Test API — ikki rejim:

TAYYORLANISH (practice):
  - Savollar `block_size` (default 25) talik bo'limlarga bo'linadi.
  - Bo'lim savollari bitta so'rovda keladi (correct_index'siz).
  - Har javob serverda tekshiriladi: natija + to'g'ri indeks qaytadi
    (o'rganish rejimi). Hech narsa serverda SAQLANMAYDI — progress
    telefon o'zida (lokal) yuritiladi. Istalgancha qayta ishlash mumkin.

IMTIHON (exam):
  - Har bo'limdan teng aralashtirilib jami `exam_question_count` (25) savol.
  - Server taymeri (`time_limit_min`): muddat o'tsa avtomatik yakun.
  - Javoblar bazaga yozilmaydi — jarayon holati Redis'da (TTL), faqat
    yakuniy ball Attempt'da qoladi.
  - To'g'ri javoblar imtihon davomida HECH QACHON oshkor qilinmaydi.
  - Qayta-qayta topshirish mumkin: har start yangi urinish ochadi.
"""
import random

from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Attempt, Question, Test, TestAccessRequest
from .serializers import (
    AccessRequestSerializer,
    QuestionPublicSerializer,
    TestListSerializer,
)

# Imtihon holati Redis kalitlari
_EXAM_STATE_KEY = "exam:state:{attempt_id}"
_EXAM_ACTIVE_KEY = "exam:active:{user_id}"
# Muddat tugagach holat yana biroz turadi (finish chaqirig'i uchun)
_STATE_SLACK_SECONDS = 600

_rng = random.SystemRandom()


def _watermark(user) -> str:
    """Backend yuboradigan watermark matni: '{full_name} · ID:{id} · {ISO}'."""
    name = user.full_name or user.email
    return f"{name} · ID:{user.id} · {timezone.now().isoformat(timespec='seconds')}"


def _is_approved(user, test) -> bool:
    return TestAccessRequest.objects.filter(
        user=user, test=test, status=TestAccessRequest.Status.APPROVED
    ).exists()


def _forbidden_not_approved():
    return Response(
        {"detail": "Testga ruxsat berilmagan.", "code": "not_approved"},
        status=status.HTTP_403_FORBIDDEN,
    )


# ============================ Umumiy ============================


class TestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tests = Test.objects.filter(is_active=True)
        return Response(TestListSerializer(tests, many=True).data)


class RequestAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, test_id):
        test = Test.objects.filter(id=test_id, is_active=True).first()
        if test is None:
            return Response({"detail": "Test topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        try:
            req, created = TestAccessRequest.objects.get_or_create(
                user=request.user,
                test=test,
                defaults={
                    "status": TestAccessRequest.Status.PENDING,
                    "comment": str(request.data.get("comment", ""))[:500],
                },
            )
        except IntegrityError:
            req = TestAccessRequest.objects.get(user=request.user, test=test)
            created = False
        return Response(
            AccessRequestSerializer(req).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MyRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqs = TestAccessRequest.objects.filter(user=request.user).select_related("test")
        return Response(AccessRequestSerializer(reqs, many=True).data)


# ======================== TAYYORLANISH ========================


class PracticeBlockView(APIView):
    """Bo'lim savollari (25 talik). Javoblar yo'q — faqat savol+variantlar."""

    permission_classes = [IsAuthenticated]

    def get(self, request, test_id, block):
        test = Test.objects.filter(id=test_id, is_active=True).first()
        if test is None:
            return Response({"detail": "Test topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        if not _is_approved(request.user, test):
            return _forbidden_not_approved()

        size = test.block_size or 25
        block = int(block)
        if block < 1 or block > test.block_count:
            return Response(
                {"detail": "Bunday bo'lim yo'q."}, status=status.HTTP_404_NOT_FOUND
            )

        start = (block - 1) * size
        questions = list(
            test.questions.order_by("order", "id")[start:start + size]
        )
        return Response(
            {
                "test_id": test.id,
                "test_title": test.title,
                "block": block,
                "block_count": test.block_count,
                "watermark": _watermark(request.user),
                "questions": QuestionPublicSerializer(questions, many=True).data,
            }
        )


class PracticeCheckView(APIView):
    """
    Bitta javobni tekshirish (tayyorlanish rejimi).
    Natija serverda saqlanmaydi. To'g'ri indeks qaytadi — o'rganish uchun.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "practice_check"

    def post(self, request):
        try:
            question_id = int(request.data.get("question_id"))
            selected_index = int(request.data.get("selected_index"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "question_id va selected_index majburiy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = (
            Question.objects.select_related("test")
            .filter(id=question_id, test__is_active=True)
            .first()
        )
        if question is None:
            return Response({"detail": "Savol topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        if not _is_approved(request.user, question.test):
            return _forbidden_not_approved()
        if selected_index < 0 or selected_index >= len(question.options or []):
            return Response(
                {"detail": "Tanlangan variant mavjud emas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "question_id": question.id,
                "is_correct": selected_index == question.correct_index,
                "correct_index": question.correct_index,
            }
        )


# =========================== IMTIHON ===========================


def _pick_exam_questions(test) -> list[int]:
    """
    Har bo'limdan teng (round-robin) aralashtirilib `exam_question_count` ta
    savol ID tanlanadi, so'ng umumiy tartib ham aralashtiriladi.
    """
    size = test.block_size or 25
    ids = list(test.questions.order_by("order", "id").values_list("id", flat=True))
    blocks = [ids[i:i + size] for i in range(0, len(ids), size)]
    for b in blocks:
        _rng.shuffle(b)

    count = min(test.exam_question_count or 25, len(ids))
    picked: list[int] = []
    level = 0
    while len(picked) < count:
        progressed = False
        for b in blocks:
            if level < len(b) and len(picked) < count:
                picked.append(b[level])
                progressed = True
        if not progressed:
            break
        level += 1
    _rng.shuffle(picked)
    return picked


def _state_key(attempt_id) -> str:
    return _EXAM_STATE_KEY.format(attempt_id=attempt_id)


def _active_key(user_id) -> str:
    return _EXAM_ACTIVE_KEY.format(user_id=user_id)


def _load_active_state(user):
    """Foydalanuvchining joriy imtihon holati (attempt_id, state) yoki (None, None)."""
    attempt_id = cache.get(_active_key(user.id))
    if attempt_id is None:
        return None, None
    state = cache.get(_state_key(attempt_id))
    if state is None:
        cache.delete(_active_key(user.id))
        return None, None
    return attempt_id, state


def _remaining_sec(state) -> int:
    return max(0, int(state["deadline"] - timezone.now().timestamp()))


def _finalize(user, attempt_id, state) -> dict:
    """Imtihonni yakunlash: ball hisoblanadi, Redis holati o'chadi."""
    total = len(state["qids"])
    correct = int(state["correct"])
    score = round((correct / total) * 100) if total else 0

    Attempt.objects.filter(id=attempt_id, user=user).update(
        score=score,
        status=Attempt.Status.FINISHED,
        finished_at=timezone.now(),
    )
    cache.delete(_state_key(attempt_id))
    cache.delete(_active_key(user.id))
    return {"finished": True, "score": score, "correct": correct, "total": total}


class ExamStartView(APIView):
    """Yangi imtihon boshlash. Har safar yangi urinish (qayta topshirish mumkin)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "exam_start"

    def post(self, request, test_id):
        test = Test.objects.filter(id=test_id, is_active=True).first()
        if test is None:
            return Response({"detail": "Test topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        if not _is_approved(request.user, test):
            return _forbidden_not_approved()
        if not test.questions.exists():
            return Response(
                {"detail": "Testda savollar yo'q."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Oldingi tugallanmagan imtihon bo'lsa — bekor qilamiz (yangi boshlanadi)
        old_attempt_id, _old_state = _load_active_state(request.user)
        if old_attempt_id is not None:
            cache.delete(_state_key(old_attempt_id))
            cache.delete(_active_key(request.user.id))
        Attempt.objects.filter(
            user=request.user, status=Attempt.Status.ACTIVE
        ).update(status=Attempt.Status.VOID, finished_at=timezone.now())

        qids = _pick_exam_questions(test)
        attempt = Attempt.objects.create(
            user=request.user, test=test, mode=Attempt.Mode.EXAM
        )
        time_limit_sec = (test.time_limit_min or 25) * 60
        state = {
            "test_id": test.id,
            "qids": qids,
            "idx": 0,
            "correct": 0,
            "deadline": timezone.now().timestamp() + time_limit_sec,
        }
        ttl = time_limit_sec + _STATE_SLACK_SECONDS
        cache.set(_state_key(attempt.id), state, timeout=ttl)
        cache.set(_active_key(request.user.id), attempt.id, timeout=ttl)

        return Response(
            {
                "attempt_id": attempt.id,
                "test_title": test.title,
                "time_limit_min": test.time_limit_min,
                "total": len(qids),
                "remaining_sec": time_limit_sec,
            },
            status=status.HTTP_200_OK,
        )


class ExamQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        attempt_id, state = _load_active_state(request.user)
        if state is None:
            return Response(
                {"detail": "Faol imtihon yo'q.", "code": "no_active_attempt"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Muddat tugagan — avtomatik yakun
        if _remaining_sec(state) <= 0:
            return Response(_finalize(request.user, attempt_id, state))

        total = len(state["qids"])
        idx = int(state["idx"])
        if idx >= total:
            return Response(
                {
                    "finished": True,
                    "total": total,
                    "answered": idx,
                    "watermark": _watermark(request.user),
                }
            )

        question = Question.objects.filter(id=state["qids"][idx]).first()
        if question is None:  # savol o'chirilgan bo'lsa — o'tkazib yuboramiz
            state["idx"] = idx + 1
            cache.set(_state_key(attempt_id), state, timeout=_remaining_sec(state) + _STATE_SLACK_SECONDS)
            return self.get(request)

        payload = QuestionPublicSerializer(question).data
        payload.update(
            {
                "index": idx,
                "number": idx + 1,
                "total": total,
                "finished": False,
                "remaining_sec": _remaining_sec(state),
                "watermark": _watermark(request.user),
            }
        )
        return Response(payload)


class ExamAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        attempt_id, state = _load_active_state(request.user)
        if state is None:
            return Response(
                {"detail": "Faol imtihon yo'q.", "code": "no_active_attempt"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Muddat tugagan — javob qabul qilinmaydi, yakunlanadi
        if _remaining_sec(state) <= 0:
            return Response(_finalize(request.user, attempt_id, state))

        try:
            selected_index = int(request.data.get("selected_index"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "selected_index noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST
            )

        total = len(state["qids"])
        idx = int(state["idx"])
        if idx >= total:
            return Response(_finalize(request.user, attempt_id, state))

        question = Question.objects.filter(id=state["qids"][idx]).first()
        if question is not None:
            if selected_index < 0 or selected_index >= len(question.options or []):
                return Response(
                    {"detail": "Tanlangan variant mavjud emas."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Tekshirish faqat serverda — natija oshkor qilinmaydi
            if selected_index == question.correct_index:
                state["correct"] = int(state["correct"]) + 1

        state["idx"] = idx + 1
        finished = state["idx"] >= total

        if finished:
            return Response(_finalize(request.user, attempt_id, state))

        cache.set(
            _state_key(attempt_id),
            state,
            timeout=_remaining_sec(state) + _STATE_SLACK_SECONDS,
        )
        return Response(
            {
                "finished": False,
                "number": state["idx"] + 1,
                "total": total,
                "remaining_sec": _remaining_sec(state),
            }
        )


class ExamFinishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        attempt_id, state = _load_active_state(request.user)
        if state is None:
            return Response(
                {"detail": "Faol imtihon yo'q.", "code": "no_active_attempt"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_finalize(request.user, attempt_id, state))


class MyResultsView(APIView):
    """Foydalanuvchining o'z imtihon natijalari (faqat yakuniy ballar)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        attempts = (
            Attempt.objects.filter(
                user=request.user, status=Attempt.Status.FINISHED
            )
            .select_related("test")
            .order_by("-finished_at")[:50]
        )
        return Response(
            [
                {
                    "id": a.id,
                    "test_title": a.test.title,
                    "score": a.score,
                    "finished_at": a.finished_at.isoformat() if a.finished_at else None,
                }
                for a in attempts
            ]
        )
