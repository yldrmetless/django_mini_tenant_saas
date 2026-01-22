import logging

from django.conf import settings
from requests import HTTPError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mail import send_invite_email
from core.models import Invitation, Projects
from core.pagination import Pagination10
from core.permissions import IsOrgAdmin
from core.serializers import (
    AcceptInviteSerializer,
    InvitationCancelSerializer,
    InvitationCreateSerializer,
    InvitationListSerializer,
    OrganizationCreateSerializer,
    OrganizationDetailSerializer,
    OrganizationUpdateSerializer,
    OrganizationUserListSerializer,
    OrgMemberListSerializer,
    OrgMemberRoleUpdateSerializer,
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
)
from users.models import Users

logger = logging.getLogger(__name__)


class OrganizationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = OrganizationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        org = serializer.save()

        return Response(
            {
                "status": 201,
                "message": "Organization oluşturuldu.",
                "data": OrganizationCreateSerializer(org).data,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = getattr(request.user, "organization", None)

        if not org or org.is_deleted:
            return Response(
                {
                    "status": 200,
                    "data": None,
                    "message": "Kullanıcı henüz bir organizasyona bağlı değil.",
                },
                status=status.HTTP_200_OK,
            )

        if not org.is_active:
            return Response(
                {
                    "status": 200,
                    "data": OrganizationDetailSerializer(org).data,
                    "message": "Organizasyon pasif durumda.",
                },
                status=status.HTTP_200_OK,
            )

        data = OrganizationDetailSerializer(org).data
        return Response({"status": 200, "data": data}, status=status.HTTP_200_OK)


class OrganizationMeUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def patch(self, request):
        org = getattr(request.user, "organization", None)

        if not org or org.is_deleted:
            return Response(
                {
                    "status": 200,
                    "data": None,
                    "message": "Kullanıcı bir organizasyona bağlı değil.",
                },
                status=status.HTTP_200_OK,
            )

        serializer = OrganizationUpdateSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        is_deleted_requested = serializer.validated_data.get("is_deleted", False)

        org = serializer.save()

        if is_deleted_requested:

            Users.objects.filter(organization=org).update(organization=None)

        return Response(
            {
                "status": 200,
                "message": "Organization güncellendi.",
                "data": OrganizationDetailSerializer(org).data,
            },
            status=status.HTTP_200_OK,
        )


class OrganizationInviteCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        org = getattr(request.user, "organization", None)
        if not org or org.is_deleted:
            return Response(
                {"status": 400, "message": "Önce organization oluştur."}, status=400
            )

        serializer = InvitationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        invite = serializer.save()

        invite_link = f"{settings.FRONTEND_BASE_URL}/accept-invite?token={invite.token}"

        try:
            send_invite_email(
                to_email=invite.email, invite_link=invite_link, org_name=org.name
            )
            msg = "Davet gönderildi."
            email_delivery = "sent"
        except HTTPError as e:
            logger.warning("Mailgun invite send failed: %s", str(e), exc_info=True)
            INVITE_EMAIL_FAILED_MESSAGE = (
                "Davet oluşturuldu; e-posta gönderilemedi. "
                "Davet linkini kopyalayıp paylaşın."
            )
            msg = INVITE_EMAIL_FAILED_MESSAGE
            email_delivery = "failed"

        return Response(
            {
                "status": 201,
                "message": msg,
                "data": {
                    "email": invite.email,
                    "token": str(invite.token),
                    "invite_link": invite_link,
                    "email_delivery": email_delivery,
                },
            },
            status=201,
        )


class AcceptInviteAPIView(APIView):
    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "status": 201,
                "message": "Davet kabul edildi, kayıt tamamlandı.",
                "data": {"id": user.id, "username": user.username, "email": user.email},
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationMembersListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    pagination_class = Pagination10

    def get(self, request):
        org = getattr(request.user, "organization", None)

        if not org or org.is_deleted:
            return Response(
                {"status": 200, "message": "Organization bulunamadı.", "data": []},
                status=status.HTTP_200_OK,
            )

        queryset = Users.objects.filter(organization=org, is_deleted=False).order_by(
            "-date_joined"
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = OrgMemberListSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class OrganizationMemberRoleUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def patch(self, request, id):
        try:
            target_user = Users.objects.get(id=id, is_deleted=False)
        except Users.DoesNotExist:
            return Response(
                {"status": 404, "message": "Kullanıcı bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OrgMemberRoleUpdateSerializer(
            instance=target_user,
            data=request.data,
            partial=True,
            context={"request": request, "target_user": target_user},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if request.data.get("is_deleted") is True:
            msg = "Üye silindi."
        elif request.data.get("user_type") == 1:
            msg = "Üye admin yapıldı."
        else:
            msg = "Güncellendi."

        return Response({"status": 200, "message": msg}, status=status.HTTP_200_OK)


class OrganizationInvitationsListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    pagination_class = Pagination10

    def get(self, request):
        org = getattr(request.user, "organization", None)
        if not org or org.is_deleted:
            return Response(
                {"detail": "Organization bulunamadı."}, status=status.HTTP_404_NOT_FOUND
            )

        status_param = (request.query_params.get("status") or "pending").lower().strip()

        qs = Invitation.objects.select_related("organization", "invited_by").filter(
            organization=org
        )

        if status_param == "pending":
            qs = qs.filter(is_used=False)
        elif status_param == "used":
            qs = qs.filter(is_used=True)
        elif status_param == "all":
            pass
        else:
            return Response(
                {"detail": "Geçersiz status parametresi. pending|used|all"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = qs.order_by("-expires_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = InvitationListSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class OrganizationInvitationCancelAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def patch(self, request, id):
        try:
            invite = Invitation.objects.get(id=id)
        except Invitation.DoesNotExist:
            return Response(
                {"detail": "Davet bulunamadı."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = InvitationCancelSerializer(
            instance=invite, data={}, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"detail": "Davet iptal edildi."}, status=status.HTTP_200_OK)


class ProjectCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = ProjectCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        project = serializer.save()

        return Response(
            {
                "status": 201,
                "message": "Project oluşturuldu.",
                "data": ProjectCreateSerializer(project).data,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationUsersAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    pagination_class = Pagination10

    def get(self, request):
        user = request.user
        org = getattr(user, "organization", None)

        if not org:
            return Response(
                {
                    "status": 400,
                    "message": "Kullanıcıya bağlı bir organization bulunamadı.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.user_type != 1:
            return Response(
                {"status": 403, "message": "Bu listeyi görme yetkin yok."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = Users.objects.filter(
            organization=org,
            is_active=True,
            is_deleted=False,
        ).order_by("-date_joined")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = OrganizationUserListSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class ProjectListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    pagination_class = Pagination10

    def get(self, request):
        user = request.user
        org = getattr(user, "organization", None)

        if not org:
            return Response(
                {"status": 404, "message": "Organization bulunamadı."}, status=404
            )

        queryset = Projects.objects.filter(organization=org, is_deleted=False).order_by(
            "-created_at"
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = ProjectListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class MyAppointedProjectsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        user = request.user
        org = getattr(user, "organization", None)

        if not org:
            return Response(
                {"status": 404, "message": "Organization bulunamadı."}, status=404
            )

        queryset = Projects.objects.filter(
            organization=org, appointed_person=user, is_deleted=False
        ).order_by("-created_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = ProjectListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ProjectUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        user = request.user
        org = getattr(user, "organization", None)

        if not org:
            return Response(
                {"status": 404, "message": "Organization bulunamadı."}, status=404
            )

        project = Projects.objects.filter(
            id=id, organization=org, is_deleted=False
        ).first()

        if not project:
            return Response(
                {"status": 404, "message": "Project bulunamadı."}, status=404
            )

        is_admin_or_tester = getattr(user, "user_type", None) in (1, 3)
        is_appointed = getattr(project, "appointed_person_id", None) == user.id

        if not (is_admin_or_tester or is_appointed):
            return Response(
                {"status": 403, "message": "Bu project için yetkin yok."}, status=403
            )

        serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    "status": 400,
                    "message": "Validation error.",
                    "errors": serializer.errors,
                },
                status=400,
            )

        serializer.save()

        try:
            data = ProjectListSerializer(project).data
        except Exception:
            data = ProjectUpdateSerializer(project).data

        return Response(
            {"status": 200, "message": "Project güncellendi.", "data": data}, status=200
        )


class ProjectDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        user = request.user
        org = getattr(user, "organization", None)

        if not org:
            return Response(
                {"status": 404, "message": "Organization bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        project = (
            Projects.objects.filter(id=id, organization=org, is_deleted=False)
            .select_related("appointed_person")
            .first()
        )

        if not project:
            return Response(
                {"status": 404, "message": "Project bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectListSerializer(project)
        return Response(
            {
                "status": 200,
                "message": "Project detayı getirildi.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
