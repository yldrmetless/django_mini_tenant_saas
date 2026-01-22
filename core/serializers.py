from datetime import timedelta

from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from core.models import Invitation, Organization, Projects
from users.models import Users


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "plan", "max_users")
        read_only_fields = ("id",)
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
        }

    def validate_slug(self, value):
        if value is None:
            return value

        value = slugify(value or "")
        if not value:
            raise serializers.ValidationError("Slug geçersiz.")
        if Organization.objects.filter(slug__iexact=value).exists():
            raise serializers.ValidationError("Bu slug zaten kullanılıyor.")
        return value

    def _generate_unique_slug(self, name: str) -> str:
        base = slugify(name or "") or "org"
        candidate = base
        i = 2
        while Organization.objects.filter(slug__iexact=candidate).exists():
            candidate = f"{base}-{i}"
            i += 1
        return candidate

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        raw_slug = validated_data.get("slug", None)
        if not raw_slug:
            validated_data["slug"] = self._generate_unique_slug(
                validated_data.get("name", "")
            )

        org = Organization.objects.create(
            owner_email=user.email or None, **validated_data
        )

        user.organization = org
        user.save(update_fields=["organization"])

        return org


class OrganizationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "owner_email",
            "plan",
            "max_users",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        )


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("name", "slug", "plan", "max_users", "is_active", "is_deleted")
        extra_kwargs = {
            "name": {"required": False},
            "slug": {"required": False},
            "plan": {"required": False},
            "max_users": {"required": False},
            "is_active": {"required": False},
        }

    def validate_slug(self, value):
        value = slugify(value or "")
        if not value:
            raise serializers.ValidationError("Slug geçersiz.")

        org = self.instance
        qs = Organization.objects.filter(slug__iexact=value)
        if org:
            qs = qs.exclude(id=org.id)

        if qs.exists():
            raise serializers.ValidationError("Bu slug zaten kullanılıyor.")

        return value

    def validate_max_users(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Maksimum kullanıcı sayısı en az 1 olmalıdır."
            )
        return value


class InvitationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ("id", "email")

    def create(self, validated_data):
        request = self.context["request"]
        org = request.user.organization

        invite = Invitation.objects.create(
            organization=org,
            email=validated_data["email"],
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=2),
        )
        return invite


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        token = attrs["token"]

        try:
            invite = Invitation.objects.select_related("organization").get(token=token)
        except Invitation.DoesNotExist:
            raise serializers.ValidationError(
                {"token": "Geçersiz davet token."}
            ) from None

        if invite.is_used:
            raise serializers.ValidationError({"token": "Bu davet zaten kullanılmış."})

        if timezone.now() >= invite.expires_at:
            raise serializers.ValidationError({"token": "Davetin süresi dolmuş."})

        if attrs["email"].lower() != invite.email.lower():
            raise serializers.ValidationError(
                {"email": "Bu davet bu email için oluşturulmamış."}
            )

        attrs["invite"] = invite
        return attrs

    def create(self, validated_data):
        invite = validated_data.pop("invite")
        validated_data.pop("token", None)

        password = validated_data.pop("password")

        user = Users.objects.filter(email__iexact=validated_data["email"]).first()
        if user:
            if user.organization_id and user.organization_id != invite.organization_id:
                raise serializers.ValidationError(
                    "Kullanıcı başka bir organization'a bağlı."
                )
        else:
            user = Users(**validated_data)  # sadece username + email kaldı

        user.organization = invite.organization
        user.user_type = 2
        user.set_password(password)
        user.is_active = True
        user.is_deleted = False
        user.save()

        invite.is_used = True
        invite.save(update_fields=["is_used"])

        return user


class OrgMemberListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "user_type",
            "is_active",
            "date_joined",
        )


USER_TYPE_ADMIN = 1
USER_TYPE_MEMBER = 2


class OrgMemberRoleUpdateSerializer(serializers.Serializer):
    user_type = serializers.ChoiceField(
        choices=[USER_TYPE_ADMIN, USER_TYPE_MEMBER], required=False
    )
    is_deleted = serializers.BooleanField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        target_user: Users = self.context["target_user"]

        if (
            not request.user.organization_id
            or target_user.organization_id != request.user.organization_id
        ):
            raise serializers.ValidationError(
                "Bu kullanıcı sizin organization'ınıza ait değil."
            )

        if target_user.id == request.user.id:
            raise serializers.ValidationError(
                "Kendi rolünüzü bu endpoint üzerinden değiştiremezsiniz."
            )

        wants_delete = attrs.get("is_deleted") is True
        wants_role_change = "user_type" in attrs

        if not wants_delete and not wants_role_change:
            raise serializers.ValidationError("Gönderilecek bir alan yok.")

        if wants_delete:
            if target_user.user_type == USER_TYPE_ADMIN:
                raise serializers.ValidationError(
                    "Admin kullanıcı bu endpoint ile silinemez."
                )
            return attrs

        new_role = attrs.get("user_type")

        if target_user.user_type == USER_TYPE_ADMIN and new_role == USER_TYPE_MEMBER:
            raise serializers.ValidationError("Admin kullanıcı member'a düşürülemez.")

        if target_user.user_type == USER_TYPE_MEMBER and new_role == USER_TYPE_ADMIN:
            return attrs

        raise serializers.ValidationError("Bu rol değişimi için izin yok.")

    def update(self, instance, validated_data):
        if validated_data.get("is_deleted") is True:
            instance.is_deleted = True
            instance.is_active = False
            instance.organization = None
            instance.user_type = USER_TYPE_MEMBER
            instance.save(
                update_fields=["is_deleted", "is_active", "organization", "user_type"]
            )
            return instance

        if validated_data.get("user_type") == USER_TYPE_ADMIN:
            instance.user_type = USER_TYPE_ADMIN
            instance.save(update_fields=["user_type"])
            return instance

        return instance


class InvitationListSerializer(serializers.ModelSerializer):
    invited_by_username = serializers.CharField(
        source="invited_by.username", read_only=True
    )
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )

    class Meta:
        model = Invitation
        fields = (
            "id",
            "email",
            "token",
            "is_used",
            "expires_at",
            "created_at",
            "invited_by_username",
            "organization_name",
        )


class InvitationCancelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ()

    def validate(self, attrs):
        invite = self.instance
        request = self.context["request"]

        if invite.organization_id != request.user.organization_id:
            raise serializers.ValidationError("Bu davet başka organization'a ait.")

        if invite.is_used:
            raise serializers.ValidationError(
                "Bu davet zaten kullanılmış veya iptal edilmiş."
            )

        return attrs

    def save(self, **kwargs):
        invite = self.instance
        invite.is_used = True
        invite.save(update_fields=["is_used"])
        return invite


class ProjectCreateSerializer(serializers.ModelSerializer):
    appointed_person = serializers.PrimaryKeyRelatedField(
        queryset=Users.objects.filter(is_deleted=False, is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Projects
        fields = [
            "id",
            "name",
            "description",
            "status",
            "appointed_person",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_appointed_person(self, appointed_user):
        request = self.context["request"]
        org = request.user.organization

        if appointed_user and appointed_user.organization_id != org.id:
            raise serializers.ValidationError(
                "Atanan kişi aynı organization içinde olmalı."
            )
        return appointed_user

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        org = user.organization

        return Projects.objects.create(
            organization=org, created_by=user, **validated_data
        )


class OrganizationUserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "user_type",
            "date_joined",
        ]


class ProjectListSerializer(serializers.ModelSerializer):
    appointed_person = serializers.SerializerMethodField()

    class Meta:
        model = Projects
        fields = [
            "id",
            "name",
            "description",
            "status",
            "appointed_person",
            "created_at",
            "updated_at",
        ]

    def get_appointed_person(self, obj):
        if not obj.appointed_person:
            return None

        user = obj.appointed_person
        return {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projects
        fields = ["name", "description", "status", "is_deleted"]

    def validate_status(self, value):
        allowed = {c[0] for c in Projects._meta.get_field("status").choices}
        if value not in allowed:
            raise serializers.ValidationError("Geçersiz status değeri.")
        return value
