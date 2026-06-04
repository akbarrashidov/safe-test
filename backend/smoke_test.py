"""
Uchidan-uchiga oqim smoke testi (SQLite + locmem).
Ishga tushirish:
  SECRET_KEY=dev DJANGO_SETTINGS_MODULE=config.settings_test python smoke_test.py
"""
import io
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
os.environ.setdefault("SECRET_KEY", "dev")
django.setup()

from django.core.management import call_command
from rest_framework.test import APIClient

call_command("migrate", run_syncdb=True, verbosity=0)

from PIL import Image

from accounts.models import Device, User
from alerts.models import AdminAlert
from exams.models import Attempt, Question, Test, TestAccessRequest

client = APIClient()
FAILS = []


def check(name, cond):
    print(("OK  " if cond else "FAIL") + " | " + name)
    if not cond:
        FAILS.append(name)


def fake_selfie(name="selfie.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (320, 320), (120, 90, 60)).save(buf, format="JPEG")
    buf.seek(0)
    buf.name = name
    return buf


# 1. Ro'yxatdan o'tish — selfie MAJBURIY (multipart)
r = client.post("/api/auth/register/", {
    "full_name": "Ali Valiyev", "email": "ali@example.com",
    "phone": "+998901112233", "password": "Parol#12345",
}, format="multipart")
check("selfiesiz register 400", r.status_code == 400)

r = client.post("/api/auth/register/", {
    "full_name": "Ali Valiyev", "email": "ali@example.com",
    "phone": "+998901112233", "password": "Parol#12345",
    "selfie": fake_selfie(),
}, format="multipart")
check("register 201", r.status_code == 201)
check("selfie bazada saqlandi",
      bool(User.objects.get(email="ali@example.com").selfie_data))

# 2. Birinchi login -> primary device
r = client.post("/api/auth/login/", {
    "email": "ali@example.com", "password": "Parol#12345",
    "android_id": "DEVICE_AAA", "model": "Pixel 7", "os_version": "14",
}, format="json")
check("login 200", r.status_code == 200)
access = r.data.get("access")
check("access token mavjud", bool(access))
check("primary device yaratildi",
      Device.objects.filter(is_primary=True, android_id="DEVICE_AAA").exists())

client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

# 3. Test + savollar (60 ta -> 3 bo'lim, har birida 20+ savol uchun block_size=20)
test = Test.objects.create(
    title="Sinov testi", time_limit_min=10, is_active=True,
    block_size=20, exam_question_count=25,
)
for i in range(1, 61):
    Question.objects.create(
        test=test, order=i, text=f"Savol {i}?",
        options=["A", "B", "C", "D"], correct_index=i % 4,
    )

# 4. Testlar ro'yxati — meta to'liq
r = client.get("/api/tests/")
check("tests list 200", r.status_code == 200)
t = next(x for x in r.data if x["id"] == test.id)
check("block_count=3", t["block_count"] == 3)
check("exam_question_count=25", t["exam_question_count"] == 25)

# 5. Ruxsatsiz: practice ham exam ham 403
r = client.get(f"/api/practice/{test.id}/block/1/")
check("ruxsatsiz practice 403", r.status_code == 403)
r = client.post(f"/api/exam/start/{test.id}/", {}, format="json")
check("ruxsatsiz exam 403", r.status_code == 403)

# 6. Zayavka + tasdiqlash
r = client.post(f"/api/tests/{test.id}/request/", {}, format="json")
check("zayavka 201", r.status_code == 201)
TestAccessRequest.objects.filter(user__email="ali@example.com", test=test).update(
    status="approved")

# 7. TAYYORLANISH: bo'lim savollari + javob tekshirish
r = client.get(f"/api/practice/{test.id}/block/1/")
check("practice block 200", r.status_code == 200)
check("blockda 20 savol", len(r.data["questions"]) == 20)
check("practice'da correct_index yo'q",
      all("correct_index" not in q for q in r.data["questions"]))
check("watermark mavjud", "Ali Valiyev" in r.data.get("watermark", ""))

q1 = r.data["questions"][0]  # order=1, correct=1
r = client.post("/api/practice/check/",
                {"question_id": q1["id"], "selected_index": 1}, format="json")
check("practice check to'g'ri", r.status_code == 200 and r.data["is_correct"] is True)
r = client.post("/api/practice/check/",
                {"question_id": q1["id"], "selected_index": 0}, format="json")
check("practice check noto'g'ri + correct_index qaytdi",
      r.data["is_correct"] is False and r.data["correct_index"] == 1)

# Practice'da DB'ga hech narsa yozilmadi
check("practice'da Attempt yo'q", Attempt.objects.count() == 0)

# 8. IMTIHON: start -> 25 ta aralash savol, server taymeri
r = client.post(f"/api/exam/start/{test.id}/", {}, format="json")
check("exam start 200", r.status_code == 200)
check("exam total=25", r.data["total"] == 25)
check("remaining_sec > 0", r.data["remaining_sec"] > 0)
attempt_id = r.data["attempt_id"]

seen_orders = []
finished_data = None
for step in range(25):
    r = client.get("/api/exam/question/")
    check(f"exam savol {step+1} 200", r.status_code == 200) if step == 0 else None
    if r.data.get("finished"):
        break
    assert "correct_index" not in r.data, "correct_index sizdi!"
    seen_orders.append(r.data["order"])
    # hammasiga 0-variant deb javob beramiz
    r = client.post("/api/exam/answer/", {"selected_index": 0}, format="json")
    if r.data.get("finished"):
        finished_data = r.data
        break

check("imtihon yakunlandi", finished_data is not None and finished_data["finished"])
check("ball hisoblandi (0-100)", 0 <= finished_data["score"] <= 100)
# har bo'limdan savol kelgan (1-20, 21-40, 41-60 oraliqlaridan)
check("1-bo'limdan savol bor", any(1 <= o <= 20 for o in seen_orders))
check("2-bo'limdan savol bor", any(21 <= o <= 40 for o in seen_orders))
check("3-bo'limdan savol bor", any(41 <= o <= 60 for o in seen_orders))

att = Attempt.objects.get(id=attempt_id)
check("attempt finished + score saqlandi", att.status == "finished")

# 9. QAYTA topshirish mumkin
r = client.post(f"/api/exam/start/{test.id}/", {}, format="json")
check("qayta exam start 200", r.status_code == 200)
r = client.post("/api/exam/finish/", {}, format="json")
check("qayta exam finish 200", r.status_code == 200)
check("2 ta finished attempt",
      Attempt.objects.filter(status="finished").count() == 2)

# 10. Natijalar ro'yxati
r = client.get("/api/exam/my-results/")
check("my-results 200", r.status_code == 200 and len(r.data) == 2)

# 11. IKKINCHI QURILMA: ikkala sessiya o'chadi + ruxsat reject
r2 = client.post("/api/auth/login/", {
    "email": "ali@example.com", "password": "Parol#12345",
    "android_id": "DEVICE_BBB", "model": "Galaxy", "os_version": "13",
}, format="json")
check("ikkinchi qurilma 403", r2.status_code == 403)
check("second_device alert yozildi",
      AdminAlert.objects.filter(kind="second_device").exists())
check("ikkinchi qurilma bloklandi",
      Device.objects.filter(android_id="DEVICE_BBB", is_blocked=True).exists())
check("ruxsat avtomatik reject bo'ldi",
      TestAccessRequest.objects.filter(
          user__email="ali@example.com", test=test, status="rejected").exists())

# Birinchi qurilma ham chiqarildi (sessiya o'chgan -> 401)
r = client.get("/api/tests/")
check("birinchi qurilma ham 401", r.status_code == 401)

# 12. Alert report (yangi login bilan)
TestAccessRequest.objects.filter(user__email="ali@example.com").update(status="approved")
r = client.credentials()  # tozalash
r = client.post("/api/auth/login/", {
    "email": "ali@example.com", "password": "Parol#12345",
    "android_id": "DEVICE_AAA", "model": "Pixel 7", "os_version": "14",
}, format="json")
check("primary qayta login 200", r.status_code == 200)
client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
r = client.post("/api/alerts/report/", {
    "kind": "root_detected", "detail": "su topildi", "device_info": "Pixel 7",
}, format="json")
check("alert report 200", r.status_code == 200)
r = client.get("/api/tests/")
check("alert'dan keyin 401", r.status_code == 401)

print("\n" + ("=" * 40))
if FAILS:
    print(f"XATOLAR: {len(FAILS)} ta -> {FAILS}")
    raise SystemExit(1)
print("BARCHA SMOKE TESTLAR O'TDI [OK]")
