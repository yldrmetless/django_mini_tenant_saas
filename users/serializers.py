from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8, required=False)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password2",
        )

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email zaten kullanılıyor.")
        return value

    def validate_username(self, value):
        if value and User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu kullanıcı adı zaten kullanılıyor.")
        return value

    def validate(self, attrs):
        p1 = attrs.get("password")
        p2 = attrs.get("password2")
        if p2 is not None and p1 != p2:
            raise serializers.ValidationError({"password2": "Şifreler eşleşmiyor."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password")

        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Kullanıcı adı veya şifre hatalı.")

        if not user.is_active:
            raise serializers.ValidationError("Bu hesap pasif.")

        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        user = validated_data["user"]
        refresh = RefreshToken.for_user(user)

        access_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]

        access_expires_in_minutes = int(access_lifetime.total_seconds() / 60)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "expire_time": access_expires_in_minutes,
        }


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, max_length=150)

    current_password = serializers.CharField(required=False, write_only=True)
    new_password = serializers.CharField(required=False, write_only=True, min_length=8)
    new_password2 = serializers.CharField(required=False, write_only=True, min_length=8)

    def validate_username(self, value):
        user = self.context["request"].user
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Kullanıcı adı boş olamaz.")
        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Bu kullanıcı adı zaten kullanılıyor.")
        return value

    def validate_email(self, value):
        user = self.context["request"].user
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Email boş olamaz.")
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Bu email zaten kullanılıyor.")
        return value

    def validate(self, attrs):
        wants_password_change = any(
            k in attrs for k in ("current_password", "new_password", "new_password2")
        )

        if wants_password_change:
            cp = attrs.get("current_password")
            np1 = attrs.get("new_password")
            np2 = attrs.get("new_password2")

            if not cp:
                raise serializers.ValidationError("Mevcut şifre zorunlu.")

            if not np1:
                raise serializers.ValidationError("Yeni şifre zorunlu.")

            if not np2:
                raise serializers.ValidationError("Yeni şifre tekrar zorunlu.")

            if np1 != np2:
                raise serializers.ValidationError("Yeni şifreler eşleşmiyor.")

            user = self.context["request"].user

            if not user.check_password(cp):
                raise serializers.ValidationError("Mevcut şifre hatalı.")

        return attrs

    def update(self, instance, validated_data):
        new_password = validated_data.pop("new_password", None)
        validated_data.pop("new_password2", None)
        validated_data.pop("current_password", None)

        for field in ("first_name", "last_name", "email", "username"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        if new_password:
            instance.set_password(new_password)

        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "user_type",
            "is_active",
            "date_joined",
            "organization",
        )

    def get_organization(self, obj):
        org = getattr(obj, "organization", None)
        if not org or getattr(org, "is_deleted", False):
            return None
        return {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan,
            "max_users": org.max_users,
            "is_active": org.is_active,
        }
