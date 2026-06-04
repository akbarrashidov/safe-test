# Qilingan ishlar — SecureTest platformasi

**Sana:** 2026-06-04
**Tarkib:** Django backend (Docker) + Android ilova (Kotlin/Compose) + deploy/build infratuzilmasi.
Asos: `TZ.md` + keyingi qo'shimcha talablar.

---

## 1. Backend (Django 5 + DRF + PostgreSQL 16 + Redis 7)

`backend/` — to'liq noldan yozilgan, Docker Compose'da ishlaydi.

### Ilovalar
| Ilova | Vazifa |
|---|---|
| `accounts` | Email+parol auth (JWT Bearer), device binding, bitta aktiv sessiya, selfie |
| `exams` | Testlar, zayavkalar, tayyorlanish/imtihon rejimlari |
| `alerts` | Xavfsizlik signallari (root, FLAG_SECURE, tamper) — log + darhol blok |

### Asosiy xavfsizlik mexanizmlari
- **To'g'ri javoblar hech qachon ilovaga yuborilmaydi** (imtihonda; tayyorlanishda
  javob tekshirilgach o'rganish uchun qaytadi).
- **Device binding:** birinchi login qilingan qurilma `primary`. Boshqa qurilmadan
  kirish → **ikkala sessiya o'chadi** + barcha test ruxsatlari **avto-reject** +
  qurilma blok + `AdminAlert`.
- **Bitta aktiv sessiya:** JWT ichida `session_id`, Redis'dagi joriy bilan
  solishtiriladi (`SingleSessionMiddleware`) — eski sessiya 401 oladi.
- **Watermark:** har savol javobida `{F.I.Sh.} · ID:{id} · {vaqt}` matni keladi,
  ilova ekran ustiga chizadi (kameradan suratga olishga qarshi iz).
- **Selfie registratsiyada majburiy** (multipart, ≤5MB, JPEG/PNG/WebP, Pillow bilan
  tekshiriladi, UUID nom bilan saqlanadi). Media nginx orqali OCHIQ BERILMAYDI —
  faqat admin himoyalangan view (`/api/auth/selfie/<id>/`) orqali ko'radi.
- **Throttling (Redis):** login/register/refresh 10/min, anon 30/min,
  user 240/min, practice-check 120/min, exam-start 10/min.
- **Parol:** Django validatorlari (min 8, oddiy parollar taqiqlangan, faqat raqam emas).
- **Prod sarlavhalar:** HSTS, nosniff, X-Frame DENY, secure cookie (DEBUG=False'da).
- **Alert kelganda:** sessiya o'chadi, faol urinish `void`, ilova chiqib ketadi.

### Test rejimlari
- **Tayyorlanish (practice):**
  - Savollar `block_size` (25) talik bo'limlarga bo'linadi (380 savol → 16 bo'lim).
  - `GET /api/practice/{test}/block/{n}/` — bo'lim savollari (javobsiz) + watermark.
  - `POST /api/practice/check/` — bitta javob tekshiriladi, `is_correct` +
    `correct_index` qaytadi. **Serverda hech narsa saqlanmaydi** — progress telefonda.
  - Istalgancha qayta ishlash mumkin.
- **Imtihon (exam):**
  - `POST /api/exam/start/{test}/` — har bo'limdan teng aralashtirilib
    `exam_question_count` (25) savol tanlanadi, server taymeri
    (`time_limit_min` = 25 daqiqa) ishga tushadi.
  - Jarayon holati **faqat Redis'da** (TTL bilan) — savol-javoblar bazaga yozilmaydi,
    `Attempt`da faqat yakuniy ball qoladi (`Answer` modeli umuman o'chirilgan).
  - Muddat tugasa server avto-yakunlaydi. Qayta-qayta topshirish mumkin.
  - `GET /api/exam/my-results/` — o'z natijalari ro'yxati.

### Endpointlar (qisqa)
```
POST /api/auth/register/        multipart: full_name, email, phone, password, selfie
POST /api/auth/login/           email, password, android_id, model, os_version
POST /api/auth/refresh/  /logout/   GET /api/auth/me/
GET  /api/auth/selfie/<id>/     faqat admin (session yoki staff JWT)

GET  /api/tests/                meta: block_count, exam_question_count, time_limit...
POST /api/tests/{id}/request/   zayavka      GET /api/tests/my-requests/

GET  /api/practice/{id}/block/{n}/    POST /api/practice/check/
POST /api/exam/start/{id}/   GET /api/exam/question/
POST /api/exam/answer/       POST /api/exam/finish/    GET /api/exam/my-results/

POST /api/alerts/report/        root_detected / flag_secure_failed / tamper
```

### Django admin
- `Test`/`Question` — savollar inline, imtihon parametrlari.
- `TestAccessRequest` — ro'yxatda **foydalanuvchi selfisi** ko'rinadi,
  "Tasdiqlash"/"Rad etish" actionlari.
- `User` — selfie preview. `Device` — blok/primary boshqaruvi.
- `AdminAlert` — readonly. `Attempt` — faqat yakuniy ballar (readonly).

### Import skripti
- `backend/import_json.py` — `test.json` (`{id, question, answer_a..d, correct}`)
  formatini o'qiydi, bo'sh variantlarni tashlaydi, **variantlarni barqaror
  aralashtiradi** (to'g'ri javob doim "A"da turmasin), bir xil `--title` bilan
  qayta ishga tushirilsa testni qayta yaratadi:
  ```powershell
  docker cp test.json backend-web-1:/app/
  docker cp backend\import_json.py backend-web-1:/app/
  docker compose exec -T web python import_json.py test.json --title "Kiberxavfsizlik testi" --time-limit 25
  ```
- Hozir bazada: **«Kiberxavfsizlik testi»** — 380 savol, 16 bo'lim,
  imtihon 25 savol / 25 daqiqa.

### Test qoplami
- `backend/smoke_test.py` — 41 ta tekshiruv (SQLite+locmem, Dockersiz):
  ```powershell
  cd backend
  $env:DJANGO_SETTINGS_MODULE="config.settings_test"; $env:SECRET_KEY="dev"
  ..\.venv\Scripts\python.exe smoke_test.py
  ```
  Qopanadi: selfiesiz register 400, ikkala rejim oqimi, ruxsat 403, sessiya/qurilma
  siyosati, alert→void+401, correct_index sizmasligi va h.k. **Holat: 41/41 OK.**

---

## 2. Android ilova (`android/`, Kotlin + Jetpack Compose)

Min SDK 33, Target 35. Paket: `uz.securetest`.

### Xavfsizlik (`security/`)
- `ScreenSecurity.kt` — `FLAG_SECURE` (screenshot/screen-record/recents qora);
  o'rnatilmasa alert + blok ekrani.
- `RootCheck.kt` — su binary / root APK / test-keys / emulyator → alert + ishlamaydi.
- `DeviceId.kt` — `ANDROID_ID` + model + OS (login'da device binding).
- `CertPinning.kt` — SSL pinning (prod sertifikat hash'i qo'yilganda faollashadi;
  hash olish buyrug'i fayl kommentida va README'da).
- `SelfieUtil.kt` — kamera rasmi: EXIF bo'yicha to'g'rilash, ≤1280px, JPEG 85%.

### Data qatlami (`data/`)
- Retrofit + OkHttp + kotlinx.serialization; Bearer interceptor;
  401 → avtomatik refresh → o'tmasa logout + login ekrani (`SessionEvents`).
- `TokenStore` — DataStore + xotira kesh. `PracticeStore` — tayyorlanish
  natijalari **faqat lokal** (har bo'lim eng yaxshi %).

### Ekranlar (`ui/`)
- **Login / Register** — register'da **kamera selfie majburiy** (FileProvider,
  preview, qayta olish).
- **Testlar** — zayavka holati; `approved` bo'lsa ikkita tugma:
  **Tayyorlanish** va **Imtihon**.
- **Tayyorlanish** — bo'limlar grid'i (lokal eng yaxshi % rangli), bo'lim ichida
  bitta-bitta savol, javob darhol tekshiriladi (yashil/qizil + to'g'risi),
  bo'lim oxirida natija + «Qayta ishlash» / «Keyingi bo'lim» (ketma-ket).
- **Imtihon** — 25 aralash savol, server bilan sinxron taymer, natija faqat
  oxirida, qayta topshirish mumkin.
- **Variantlar har ko'rsatilishda aralashadi** (ekranda tasodifiy tartib,
  serverga asl indeks yuboriladi) — javob pozitsiyasini yodlab bo'lmaydi.
- **Watermark** overlay — test/tayyorlanish ekranlarida diagonal takror matn.

---

## 3. Infratuzilma / deploy holati

| Narsa | Holat / manzil |
|---|---|
| Docker stack | `backend/docker-compose.yml` — db, redis, web (gunicorn), nginx :8080 |
| Hozir ishlayapti | ha — barcha konteynerlar Up, migratsiyalar qo'llangan |
| ngrok tunnel | `https://1d08-195-158-8-218.ngrok-free.app` (ngrok.exe fonda) |
| Admin panel | `<ngrok>/admin` — `admin@securetest.uz` / `admin12345` |
| APK | `android/app/build/outputs/apk/release/app-release.apk` (~2.8MB, imzolangan) |
| Keystore | `android/release.keystore` (parollar `android/keystore.properties`) — **DEV**, prodda almashtiring |
| Lokal JDK/SDK | `tools/jdk17`, `tools/android-sdk` (build uchun o'rnatilgan) |

### nginx tuzatishlari
- `map $http_x_forwarded_proto` — ngrok/LB'dan kelgan HTTPS sxemasi saqlanadi
  (admin CSRF 403 muammosi shu bilan hal bo'lgan).
- `/media/` ochiq berilmaydi (selfie himoyasi); `/static/` ochiq.
- `settings.py`: `.ngrok-free.app` kabi nuqtali hostlar `https://*.domen`
  wildcard CSRF originga aylantiriladi.

### Qayta build qilish
```powershell
# Backend (kod o'zgargach):
cd backend; docker compose up --build -d

# APK (URL o'zgargach app/build.gradle.kts -> BASE_URL):
$env:JAVA_HOME="C:\projects\safe_test\tools\jdk17"
cd android; .\gradlew.bat assembleRelease
```

⚠️ **ngrok bepul URL har qayta ishga tushganda o'zgaradi** — yangi URL'ni
`android/app/build.gradle.kts` (`BASE_URL`, debug+release) ga yozib qayta build
qilish kerak (~2 daqiqa, keshlar iliq).

---

## 4. Prod'ga chiqishda qolgan qadamlar (qo'lda)

1. Domen + Let's Encrypt sertifikat; `nginx/default.conf`dagi HTTPS blokini ochish.
2. `.env`: `DEBUG=False`, real `ALLOWED_HOSTS`, kuchli `SECRET_KEY` va parollar.
3. `BASE_URL`ni prod domenga o'zgartirish.
4. Sertifikat pin hash'ini olish (buyruq README'da) → `CertPinning.kt` `PIN`ga
   qo'yish → APK qayta build.
5. Yangi (haqiqiy) keystore yaratish, parollarni xavfsiz saqlash.
6. Admin parolini almashtirish (`admin12345` — dev parol!).

## 5. Ma'lum cheklovlar (halol baho, TZ 0-bo'lim)

- Boshqa telefon kamerasidan rasm olishni bloklab bo'lmaydi → watermark iz qoldiradi.
- Root/emulyator aniqlash 100% emas (oddiy hollarni ushlaydi); asosiy himoya —
  javoblar serverda.
- Tayyorlanish rejimida to'g'ri javoblar (tekshiruvdan keyin) ko'rinadi — bu
  rejimning maqsadi o'rganish; imtihon savollari har safar qayta aralashadi.
- ngrok free: URL o'zgaruvchan + birinchi brauzer kirishida interstitial sahifa
  (ilovaga ta'sir qilmaydi — OkHttp UA bilan o'tadi).
