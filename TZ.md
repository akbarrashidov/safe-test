# Texnik Topshiriq (TZ) — Xavfsiz Test Platformasi

**Mahsulot:** Ruxsat asosida ishlaydigan online test platformasi.
**Komponentlar:** Android native ilova (Kotlin) + Django backend.
**Distributsiya:** APK fayl (qo'lda tarqatiladi, Google Play yo'q).
**Min Android:** API 33 (Android 13). Target: API 35.

> Bu hujjat Claude Code uchun. Claude Code shu TZ asosida ikkala loyihani
> (Android + backend) noldan quradi va oxirida APK build + backend deploy
> ga tayyor holatga keltiradi. Har faylni to'liq, ishlaydigan holda yozsin.

---

## 0. MUHIM — Himoya bo'yicha halol kelishuv

Native Android web'dan ustun, lekin baribir mutlaq emas. Aniq holat:

| Tahdid | Android'da holati |
|---|---|
| Screenshot olish | ✅ **Bloklanadi** (`FLAG_SECURE`) |
| Ekran yozuvi (screen record) | ✅ **Bloklanadi** (`FLAG_SECURE`) |
| Recent apps'da ko'rinish | ✅ Yashiriladi |
| Boshqa telefon kamerasidan rasm | ❌ Bloklab bo'lmaydi → faqat **watermark izi** |
| API javobini ushlash (proxy/root) | ⚠️ SSL pinning + javoblar backendda bilan kamaytiriladi |
| Root/emulyator orqali aralashuv | ⚠️ Aniqlanadi → blok |

**Strategiya:** `FLAG_SECURE` bilan ekran himoyasi (asosiy yutuq) + watermark izi
(kamera uchun) + to'g'ri javoblar HECH QACHON ilovaga yuborilmaydi (sizdirilgan
narsa foydasiz) + device binding + SSL pinning.

Bu TZ shu falsafaga qurilgan. Soxta "100% himoya" va'da qilinmaydi.

---

# A QISM — BACKEND (Django)

## A.1 Stack
- Django 5 + Django REST Framework
- PostgreSQL 16
- Redis 7 (sessiya + nonce)
- SimpleJWT (token auth — mobil uchun cookie emas, **Bearer token**)
- Docker Compose + Nginx + Gunicorn

> Web variantdan farq: mobil ilova bo'lgani uchun JWT **Authorization: Bearer**
> headerда yuriladi (httpOnly cookie EMAS). Tile/canvas/DevTools himoyasi
> KERAK EMAS — chunki ekranni `FLAG_SECURE` himoya qiladi, savol oddiy
> JSON matn sifatida yuborilsa bo'ladi.

## A.2 Loyiha tuzilishi
```
backend/
├── docker-compose.yml
├── .env.example
├── Dockerfile
├── entrypoint.sh
├── requirements.txt
├── nginx/default.conf
├── manage.py
├── config/            # settings, urls, wsgi, asgi
├── accounts/          # auth, device binding, sessiya
├── exams/             # test, zayavka, savol, urinish
└── alerts/            # xavfsizlik loglari
```

## A.3 `accounts` ilovasi

### Modellar
- `User(AbstractUser)`: `full_name`, `phone`.
- `Device`: `user(FK)`, `android_id`(char, unique-per-user), `model`,
  `os_version`, `first_seen`, `is_primary`(bool), `is_blocked`(bool).

### Endpointlar
- `POST /api/auth/register/` — full_name, email, phone, password.
- `POST /api/auth/login/` — email, password, **android_id**, model, os_version.
  - Birinchi login → device `is_primary=True`.
  - `android_id` primary'ga teng → kirsin.
  - Boshqa `android_id` → **403 + Device blok + AdminAlert(`second_device`)**.
  - Javob: access (15 daqiqa) + refresh token + token ichida `session_id`(uuid).
- `POST /api/auth/refresh/`
- `POST /api/auth/logout/` — Redis sessiya o'chadi.

### Bitta aktiv sessiya
- Redis kalit `session:user:{id}` → joriy `session_id`. Har login ustiga yozadi.
- `SingleSessionMiddleware`: har himoyalangan so'rovda token ichidagi `session_id`
  Redis'dagiga teng emas → **401** (eski sessiya o'lgan).

## A.4 `exams` ilovasi

### Modellar
- `Test`: `title`, `description`, `is_active`, `time_limit_min`.
- `Question`: `test(FK)`, `order`, `text`, `options`(JSON list),
  `correct_index`(int) — **HECH QACHON API javobida chiqmaydi**.
- `TestAccessRequest`: `user`, `test`, `status`(pending/approved/rejected),
  `comment`, `created_at`, `reviewed_at`, `reviewed_by(FK admin)`.
  `unique_together=(user,test)`.
- `Attempt`: `user`, `test`, `started_at`, `finished_at`, `score`,
  `current_question`, `status`(active/finished/void).
- `Answer`: `attempt`, `question`, `selected_index`, `is_correct`.

### Endpointlar
- `GET /api/tests/` — aktiv testlar (faqat metama'lumot).
- `POST /api/tests/{id}/request/` — zayavka → pending.
- `GET /api/tests/my-requests/` — o'z zayavkalari holati.
- `POST /api/exam/start/{test_id}/` — `approved` tekshiradi (yo'q → 403),
  `Attempt` ochadi.
- `GET /api/exam/question/` — joriy savol: `text`, `options`, `order`, jami soni.
  **`correct_index` yo'q.** Har javobda **watermark matni** ham qaytadi
  (`"{full_name} · ID:{id} · {ISO timestamp}"`) — ilova uni overlay qiladi.
- `POST /api/exam/answer/` — `selected_index`. Backend `correct_index` bilan
  solishtiradi, `Answer` yozadi, `current_question++`. Faqat keyingi holatni qaytaradi.
- `POST /api/exam/finish/` — ball hisoblanadi.

> Sizdirishga qarshi asosiy mexanizm: to'g'ri javoblar serverda qoladi.
> Savol matni sizib chiqsa ham javoblarsiz qiymati past, watermark esa kimligini ko'rsatadi.

## A.5 `alerts` ilovasi
- `AdminAlert`: `user`, `kind`(`second_device`/`session_conflict`/`root_detected`/
  `flag_secure_failed`/`tamper`), `detail`, `ip`, `device_info`, `created_at`,
  `action_taken`(logged/session_blocked).
- `POST /api/alerts/report/` — ilova xavf signali yuboradi (root aniqlandi,
  `FLAG_SECURE` o'rnatilmadi va h.k.). **Rejim: log + darhol blok** —
  Redis sessiya o'chadi, joriy `Attempt` `void` bo'ladi, ilova chiqib ketadi.

## A.6 Django admin (tasdiqlash)
- `TestAccessRequest`: ro'yxat + filter(status,test) + action "Tasdiqlash"/"Rad etish"
  (`status`, `reviewed_by`, `reviewed_at` yangilanadi).
- `AdminAlert`: readonly, filter(kind, action_taken).
- `Device`: blok/primary holati, qo'lda blokdan chiqarish.

## A.7 SSL pinning uchun
- Backend production HTTPS sertifikati (Let's Encrypt / Nginx). Ilova shu
  sertifikat public key hash'ini pinlaydi (B qismda).

## A.8 Docker / deploy fayllari
- `Dockerfile`: python:3.12-slim, gunicorn.
- `docker-compose.yml`: db, redis, web, nginx (port 8080→lokal, 443→prod).
- `entrypoint.sh`: migrate + collectstatic + gunicorn.
- `.env.example`: SECRET_KEY, DEBUG, ALLOWED_HOSTS, POSTGRES_*, REDIS_URL,
  JWT lifetimes.
- `nginx/default.conf`: static + reverse proxy + HTTPS (prod).

---

# B QISM — ANDROID ILOVA (Kotlin)

## B.1 Stack
- Kotlin + Jetpack Compose (UI)
- Retrofit + OkHttp (API) + kotlinx.serialization
- DataStore (token saqlash)
- Min SDK 33, Target SDK 35
- Gradle (KTS)

## B.2 Loyiha tuzilishi
```
android/
├── build.gradle.kts (project)
├── settings.gradle.kts
├── gradle/libs.versions.toml
└── app/
    ├── build.gradle.kts
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        └── java/uz/securetest/
            ├── App.kt
            ├── MainActivity.kt
            ├── data/
            │   ├── api/ (Retrofit interfeyslar, DTO)
            │   ├── TokenStore.kt
            │   └── repo/ (AuthRepo, ExamRepo)
            ├── security/
            │   ├── ScreenSecurity.kt   # FLAG_SECURE
            │   ├── DeviceId.kt         # android_id
            │   ├── RootCheck.kt        # root/emulyator aniqlash
            │   └── CertPinning.kt      # OkHttp pinner
            └── ui/
                ├── login/  register/  tests/  exam/  (Compose ekranlar)
                └── components/Watermark.kt
```

## B.3 Xavfsizlik komponentlari (ENG MUHIM QISM)

### `ScreenSecurity.kt` — screenshot/yozuv bloki
- `MainActivity.onCreate()` da:
  ```kotlin
  window.setFlags(
      WindowManager.LayoutParams.FLAG_SECURE,
      WindowManager.LayoutParams.FLAG_SECURE
  )
  ```
- Bu butun ilova bo'yicha screenshot, screen record, recent-apps preview, tashqi
  displayни bloklaydi.
- Agar biror sababdan o'rnatilmasa → `AdminAlert(flag_secure_failed)` + blok.

### `DeviceId.kt`
- `Settings.Secure.ANDROID_ID` olinadi → login'da `android_id` sifatida yuboriladi.

### `RootCheck.kt`
- Root belgilari (`su` binary, `Superuser.apk`, build tags `test-keys`),
  emulyator belgilari tekshiriladi. Topilsa → `POST /api/alerts/report/`
  (`root_detected`) + ilova ishlamaydi.

### `CertPinning.kt`
- OkHttp `CertificatePinner` bilan backend sertifikat public key hash pinlanadi.
  Proxy (Charles/Burp) orqali API ushlashni qiyinlashtiradi.

### `Watermark.kt` (Compose)
- Test ekranida butun kontent ustiga `Box` overlay: backend yuborgan watermark
  matni (`full_name · ID · vaqt`) diagonal, takror, yarim shaffof (alpha ~0.12),
  `Modifier.pointerInput`siz (bosishga xalaqit bermaydi). Telefon kamerasiga
  qarshi yagona iz.

## B.4 Ekranlar (Compose)
- **Login / Register:** email/parol/telefon; login'da android_id+model+os yuboriladi.
  401/403 → tegishli xabar (boshqa qurilma / sessiya tugagan).
- **Testlar ro'yxati:** aktiv testlar; har biriga "Zayavka tashlash" tugmasi;
  zayavka holati ko'rinadi (pending/approved/rejected).
- **Test ekrani:** faqat `approved` bo'lsa ochiladi. Bitta savol + variantlar
  (RadioButton), watermark overlay, "Keyingi" tugmasi, taymer (`time_limit_min`).
  Javob tanlanib yuborilгач keyingi savol. Oxirida natija.
- Har API 401 → login'ga otadi (sessiya o'lgan).

## B.5 Token / sessiya
- Access token DataStore'da; har so'rovda `Authorization: Bearer`.
- 401 da refresh urinadi; refresh ham 401 → logout + login ekrani.

---

# C QISM — BUILD VA DEPLOY (oxirgi bosqich)

## C.1 Backend deploy (Docker)
Lokal/server bir xil:
```bash
cd backend
cp .env.example .env          # qiymatlarni to'ldiring
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
# Admin: http(s)://<host>/admin
```
Production'da: Nginx + Let's Encrypt sertifikat, `DEBUG=False`,
`ALLOWED_HOSTS` to'g'ri. Sertifikat o'rnatilgach uning public key hash'ini
oling (B.3 CertPinning uchun):
```bash
openssl s_client -connect <domen>:443 | openssl x509 -pubkey -noout \
 | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
```
Chiqqan hash'ni `CertPinning.kt`'ga qo'ying.

## C.2 Android APK build
```bash
cd android
# release uchun keystore yaratish (bir marta)
keytool -genkey -v -keystore release.keystore -alias securetest \
  -keyalg RSA -keysize 2048 -validity 10000
# build.gradle.kts'da signingConfig'ni keystore'ga ulang
./gradlew assembleRelease
# APK manzili:
# app/build/outputs/apk/release/app-release.apk
```
- `build.gradle.kts`'da backend bazaviy URL'ni `BuildConfig`ga qo'ying
  (debug=lokal, release=prod domen).
- APK'ni qo'lda tarqatiladi (Play yo'q). Foydalanuvchi "noma'lum manba"dan
  o'rnatishga ruxsat berishi kerakligini README'da yozing.

## C.3 To'liq oqim (yakuniy tekshiruv)
1. Backend ko'tariladi, admin Test + Question qo'shadi.
2. Foydalanuvchi ilovada ro'yxatdan o'tadi → birinchi qurilma primary bo'ladi.
3. Boshqa telefondan kirsa → 403 + alert + blok.
4. Testga zayavka → admin Django admin'da tasdiqlaydi.
5. Test ochiladi: `FLAG_SECURE` faol (screenshot/yozuv qora chiqadi),
   watermark ko'rinadi, savollar bittadan, javoblar serverda.
6. Root/proxy aniqlansa → blok.

---

## Claude Code uchun checklist
- [ ] Backend: `correct_index` hech qaysi API javobida yo'q.
- [ ] Backend: bitta aktiv sessiya middleware (ikkinchi login birinchisini 401 qiladi).
- [ ] Backend: ikkinchi `android_id` → 403 + AdminAlert + blok.
- [ ] Backend: `docker compose up --build` toza ko'tariladi, admin tasdiqlash actionlari bor.
- [ ] Android: `FLAG_SECURE` MainActivity'da, screenshot/yozuv bloklanadi.
- [ ] Android: android_id binding, root/emulyator check, SSL pinning.
- [ ] Android: watermark overlay (backend matni), bitta savol, Bearer token, taymer.
- [ ] Android: `./gradlew assembleRelease` bilan signed APK chiqadi.
- [ ] Har fayl to'liq yozilgan ("..." yo'q), ishlaydigan holatda.

> Tartib: backend (modellar→migrate→views→urls→admin→docker) → android
> (gradle→manifest→security→data→ui) → build/deploy ko'rsatmalari.
