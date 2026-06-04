import io

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from PIL import Image
from rest_framework import serializers

User = get_user_model()

# Selfi cheklovlari
MAX_SELFIE_MB = 5
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
SELFIE_MAX_DIM = 1024  # bazaga yozishdan oldin shu o'lchamga kichraytiriladi


def reencode_selfie(uploaded) -> bytes:
    """
    Yuklangan rasmni serverda qayta kodlash: RGB JPEG, <=1024px, sifat 85.
    Bu ham hajmni kichraytiradi, ham fayl ichiga yashirilgan har qanday
    begona ma'lumotni (EXIF, polyglot) olib tashlaydi.
    """
    uploaded.seek(0)
    img = Image.open(uploaded)
    img = img.convert("RGB")
    img.thumbnail((SELFIE_MAX_DIM, SELFIE_MAX_DIM))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    # Kameradan olingan selfi — MAJBURIY (multipart/form-data)
    selfie = serializers.ImageField(required=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return value.lower()

    def validate_password(self, value):
        # Django'ning standart parol validatorlari (min 8 belgi, oddiy parollar
        # ro'yxati, faqat raqam emas va h.k.)
        validate_password(value)
        return value

    def validate_selfie(self, value):
        if value.size > MAX_SELFIE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"Rasm hajmi {MAX_SELFIE_MB}MB dan oshmasin."
            )
        content_type = getattr(value, "content_type", "") or ""
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise serializers.ValidationError(
                "Faqat JPEG/PNG/WebP rasm qabul qilinadi."
            )
        # ImageField'ning o'zi Pillow bilan rasm ekanini tekshiradi
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data["email"]
        user = User(
            username=email,
            email=email,
            full_name=validated_data.get("full_name", ""),
            phone=validated_data.get("phone", ""),
            # Diskka emas — bazaga (efemer disk muhitlarida ham saqlanadi)
            selfie_data=reencode_selfie(validated_data["selfie"]),
        )
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    android_id = serializers.CharField(max_length=128)
    model = serializers.CharField(max_length=128, required=False, allow_blank=True)
    os_version = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Email yoki parol noto'g'ri.")
        user = authenticate(username=user.username, password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Email yoki parol noto'g'ri.")
        if not user.is_active:
            raise serializers.ValidationError("Hisob faol emas.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone"]
