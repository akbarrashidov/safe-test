# SecureTest — Xavfsiz Test Platformasi

Ruxsat asosida ishlaydigan online test platformasi:
**Android native ilova (Kotlin + Jetpack Compose)** + **Django backend**.

Himoya falsafasi (TZ 0-bo'lim): `FLAG_SECURE` (screenshot/yozuv bloki) +
watermark izi (kamera uchun) + to'g'ri javoblar **hech qachon** ilovaga
yuborilmaydi + device binding + bitta aktiv sessiya + SSL pinning +
root/emulyator aniqlash.

---

## 1. Backend ishga tushirish (Docker)

```bash
cd backend
cp .env.example .env          # qiymatlarni to'ldiring (SECRET_KEY, parollar...)
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

- API: `http://<host>:8080/api/...`
- Admin: `http://<host>:8080/admin` — bu yerda Test + Savollar qo'shiladi,
  zayavkalar tasdiqlanadi (`Tasdiqlash` / `Rad etish` action'lari),
  xavfsizlik alertlari ko'riladi, qurilmalar blokdan chiqariladi.

### Production
- `DEBUG=False`, `ALLOWED_HOSTS` to'g'ri domen.
- Nginx + Let's Encrypt HTTPS (443). Sertifikat o'rnatilgach pinning hash'ini oling:

```bash
openssl s_client -connect <domen>:443 | openssl x509 -pubkey -noout \
 | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
```

Chiqqan qiymatni `sha256/<base64>` ko'rinishida
`android/app/src/main/java/uz/securetest/security/CertPinning.kt` dagi
`PIN` o'zgaruvchisiga qo'ying.

---

## 2. Android APK build

Talablar: JDK 17, Android SDK (Android Studio bilan keladi).

```bash
cd android

# 1) Release keystore yaratish (bir marta):
keytool -genkey -v -keystore release.keystore -alias securetest \
  -keyalg RSA -keysize 2048 -validity 10000

# 2) Parollarni yozish:
cp keystore.properties.example keystore.properties
#    storePassword / keyPassword qiymatlarini to'ldiring

# 3) Backend URL'ni sozlash:
#    app/build.gradle.kts -> release buildType -> BASE_URL ga prod domeningizni qo'ying

# 4) Build:
./gradlew assembleRelease        # Windows: .\gradlew.bat assembleRelease

# APK manzili:
# app/build/outputs/apk/release/app-release.apk
```

- Debug build (`assembleDebug`) lokal backendga (`http://10.0.2.2:8080/` —
  emulyatordagi host mashina) ulanadi va cleartext'ga ruxsat bor.
- Release'da faqat HTTPS; `CertPinning.PIN` qo'yilgan bo'lsa SSL pinning faol.

### O'rnatish (foydalanuvchilarga)
APK qo'lda tarqatiladi (Google Play yo'q). Telefon "Noma'lum manbalardan
o'rnatish"ga ruxsat so'raydi: **Sozlamalar → Xavfsizlik → Noma'lum ilovalarni
o'rnatish** bo'limidan fayl menejeri/brauzerga ruxsat bering, so'ng APK'ni oching.

---

## 3. To'liq oqim (yakuniy tekshiruv)

1. Backend ko'tariladi, admin Test + Question qo'shadi.
2. Foydalanuvchi ilovada ro'yxatdan o'tadi → birinchi login qilingan qurilma
   **primary** bo'ladi.
3. Boshqa telefondan kirsa → **403** + `second_device` alert + qurilma blok.
4. Testga zayavka → admin Django admin'da tasdiqlaydi.
5. Test ochiladi: `FLAG_SECURE` faol (screenshot/yozuv qora chiqadi),
   watermark (F.I.Sh. · ID · vaqt) ko'rinadi, savollar bittadan keladi,
   to'g'ri javoblar serverda qoladi.
6. Root/emulyator aniqlansa yoki FLAG_SECURE o'rnatilmasa → alert + sessiya blok,
   joriy urinish `void`.
7. Ikkinchi qurilmadan login → birinchi sessiya keyingi so'rovda **401** oladi
   (bitta aktiv sessiya, Redis).

## 4. Loyiha tuzilishi

```
backend/   Django 5 + DRF + PostgreSQL + Redis + Docker (accounts/exams/alerts)
android/   Kotlin + Compose (data/security/ui qatlamlari)
TZ.md      Texnik topshiriq
```
