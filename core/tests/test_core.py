import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Invitation, Organization, Projects
from users.models import Users


@pytest.mark.django_db
class TestOrganizationCreateAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-create")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_org_create_requires_auth(self, client, url):
        res = client.post(
            url, {"name": "Acme", "plan": "free", "max_users": 10}, format="json"
        )
        assert res.status_code == 401

    def test_org_create_forbidden_for_non_admin(self, client, url):
        user = Users.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            user_type=2,
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, user)

        res = client.post(
            url, {"name": "Acme", "plan": "free", "max_users": 10}, format="json"
        )
        assert res.status_code == 403

    def test_org_create_success_admin_assigns_user_org(self, client, url):
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            user_type=1,  # Admin
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, admin)

        payload = {"name": "Acme", "plan": "free", "max_users": 10}
        res = client.post(url, payload, format="json")

        assert res.status_code == 201
        assert res.data["status"] == 201
        assert res.data["message"] == "Organization oluşturuldu."

        org_id = res.data["data"]["id"]
        org = Organization.objects.get(id=org_id)

        assert org.slug is not None
        assert org.slug != ""

        admin.refresh_from_db()
        assert admin.organization_id == org.id

        assert org.owner_email == "admin@example.com"

    def test_org_create_slug_duplicate_returns_400(self, client, url):
        Organization.objects.create(
            name="Existing", slug="acme", plan="free", max_users=10, owner_email=None
        )

        admin = Users.objects.create_user(
            username="admin2",
            email="admin2@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        payload = {"name": "Acme2", "slug": "acme", "plan": "free", "max_users": 10}
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "slug" in res.data

    def test_org_create_slug_invalid_returns_400(self, client, url):
        admin = Users.objects.create_user(
            username="admin3",
            email="admin3@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        payload = {"name": "Acme3", "slug": "!!!", "plan": "free", "max_users": 10}
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "slug" in res.data

    def test_org_create_slug_autogenerates_unique(self, client, url):
        admin1 = Users.objects.create_user(
            username="adminA",
            email="adminA@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin1)

        res1 = client.post(
            url, {"name": "Acme", "plan": "free", "max_users": 10}, format="json"
        )
        assert res1.status_code == 201
        org1_slug = res1.data["data"]["slug"]

        admin2 = Users.objects.create_user(
            username="adminB",
            email="adminB@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        client.force_authenticate(user=admin2)

        res2 = client.post(
            url, {"name": "Acme", "plan": "free", "max_users": 10}, format="json"
        )
        assert res2.status_code == 201
        org2_slug = res2.data["data"]["slug"]

        assert org1_slug != org2_slug
        assert org2_slug.startswith(org1_slug)


@pytest.mark.django_db
class TestOrganizationMeAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-me")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_org_me_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_org_me_returns_none_when_user_has_no_org(self, client, url):
        user = Users.objects.create_user(
            username="u1",
            email="u1@example.com",
            password="StrongPass123!",
            user_type=2,
            is_active=True,
        )
        self.auth(client, user)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["data"] is None
        assert res.data["message"] == "Kullanıcı henüz bir organizasyona bağlı değil."

    def test_org_me_returns_none_when_org_deleted(self, client, url):
        org = Organization.objects.create(
            name="DeletedOrg",
            slug="deleted-org",
            owner_email="x@example.com",
            plan="free",
            max_users=1,
            is_active=True,
            is_deleted=True,
        )
        user = Users.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="StrongPass123!",
            organization=org,
            is_active=True,
        )
        self.auth(client, user)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["data"] is None
        assert res.data["message"] == "Kullanıcı henüz bir organizasyona bağlı değil."

    def test_org_me_returns_data_and_message_when_org_inactive(self, client, url):
        org = Organization.objects.create(
            name="InactiveOrg",
            slug="inactive-org",
            owner_email="owner@example.com",
            plan="free",
            max_users=10,
            is_active=False,
            is_deleted=False,
        )
        user = Users.objects.create_user(
            username="u3",
            email="u3@example.com",
            password="StrongPass123!",
            organization=org,
            is_active=True,
        )
        self.auth(client, user)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Organizasyon pasif durumda."
        assert res.data["data"]["id"] == org.id
        assert res.data["data"]["name"] == "InactiveOrg"
        assert res.data["data"]["slug"] == "inactive-org"
        assert res.data["data"]["owner_email"] == "owner@example.com"
        assert res.data["data"]["plan"] == "free"
        assert res.data["data"]["max_users"] == 10
        assert res.data["data"]["is_active"] is False
        assert res.data["data"]["is_deleted"] is False
        assert "created_at" in res.data["data"]
        assert "updated_at" in res.data["data"]

    def test_org_me_returns_data_when_org_active(self, client, url):
        org = Organization.objects.create(
            name="ActiveOrg",
            slug="active-org",
            owner_email="owner@example.com",
            plan="free",
            max_users=5,
            is_active=True,
            is_deleted=False,
        )
        user = Users.objects.create_user(
            username="u4",
            email="u4@example.com",
            password="StrongPass123!",
            organization=org,
            is_active=True,
        )
        self.auth(client, user)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["data"]["id"] == org.id
        assert res.data["data"]["name"] == "ActiveOrg"
        assert res.data["data"]["slug"] == "active-org"
        assert res.data["data"]["owner_email"] == "owner@example.com"
        assert res.data["data"]["plan"] == "free"
        assert res.data["data"]["max_users"] == 5
        assert res.data["data"]["is_active"] is True
        assert res.data["data"]["is_deleted"] is False


@pytest.mark.django_db
class TestOrganizationMeUpdateAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-me-update")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_org_me_update_requires_auth(self, client, url):
        res = client.patch(url, {"name": "X"}, format="json")
        assert res.status_code == 401

    def test_org_me_update_forbidden_for_non_admin(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            owner_email="o@example.com",
            plan="free",
            max_users=1,
            is_active=True,
            is_deleted=False,
        )
        member = Users.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
        )
        self.auth(client, member)

        res = client.patch(url, {"name": "New"}, format="json")
        assert res.status_code == 403

    def test_org_me_update_returns_none_when_user_has_no_org(self, client, url):
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        res = client.patch(url, {"name": "New"}, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["data"] is None
        assert res.data["message"] == "Kullanıcı bir organizasyona bağlı değil."

    def test_org_me_update_returns_none_when_org_deleted(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            owner_email="o@example.com",
            plan="free",
            max_users=1,
            is_active=True,
            is_deleted=True,
        )
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        res = client.patch(url, {"name": "New"}, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["data"] is None
        assert res.data["message"] == "Kullanıcı bir organizasyona bağlı değil."

    def test_org_me_update_success_updates_fields(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            owner_email="o@example.com",
            plan="free",
            max_users=1,
            is_active=True,
            is_deleted=False,
        )
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        payload = {
            "name": "Org Updated",
            "plan": "free",
            "max_users": 10,
            "is_active": False,
        }
        res = client.patch(url, payload, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Organization güncellendi."
        assert res.data["data"]["id"] == org.id
        assert res.data["data"]["name"] == "Org Updated"
        assert res.data["data"]["max_users"] == 10
        assert res.data["data"]["is_active"] is False

        org.refresh_from_db()
        assert org.name == "Org Updated"
        assert org.max_users == 10
        assert org.is_active is False

    def test_org_me_update_is_deleted_true_unassigns_all_users(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            owner_email="o@example.com",
            plan="free",
            max_users=3,
            is_active=True,
            is_deleted=False,
        )

        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,  # Admin
            is_active=True,
        )
        member = Users.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
        )
        tester = Users.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=3,
            is_active=True,
        )

        self.auth(client, admin)

        res = client.patch(url, {"is_deleted": True}, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Organization güncellendi."
        assert res.data["data"]["id"] == org.id
        assert res.data["data"]["is_deleted"] is True

        org.refresh_from_db()
        assert org.is_deleted is True

        admin.refresh_from_db()
        member.refresh_from_db()
        tester.refresh_from_db()

        assert admin.organization is None
        assert member.organization is None
        assert tester.organization is None


@pytest.mark.django_db
class TestOrganizationInviteCreateAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-invite")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_invite_requires_auth(self, client, url):
        res = client.post(url, {"email": "x@example.com"}, format="json")
        assert res.status_code == 401

    def test_invite_forbidden_for_non_admin(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )
        member = Users.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
        )
        self.auth(client, member)

        res = client.post(url, {"email": "x@example.com"}, format="json")
        assert res.status_code == 403

    def test_invite_returns_400_if_user_has_no_org(self, client, url):
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        res = client.post(url, {"email": "x@example.com"}, format="json")
        assert res.status_code == 400
        assert res.data["status"] == 400
        assert res.data["message"] == "Önce organization oluştur."

    def test_invite_success_email_sent(self, client, url, monkeypatch, settings):
        """
        send_invite_email başarılı => message 'Davet gönderildi.'
        ve email_delivery 'sent'
        """
        org = Organization.objects.create(
            name="Org",
            slug="org",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        settings.FRONTEND_BASE_URL = "http://frontend.test"

        def fake_send_invite_email(to_email, invite_link, org_name):
            return {"ok": True}

        monkeypatch.setattr("core.views.send_invite_email", fake_send_invite_email)

        res = client.post(url, {"email": "invitee@example.com"}, format="json")

        assert res.status_code == 201
        assert res.data["status"] == 201
        assert res.data["message"] == "Davet gönderildi."

        data = res.data["data"]
        assert data["email"] == "invitee@example.com"
        assert "token" in data
        assert "invite_link" in data
        assert data["invite_link"].startswith(
            "http://frontend.test/accept-invite?token="
        )
        assert data["email_delivery"] == "sent"

        assert Invitation.objects.filter(
            email="invitee@example.com", organization=org
        ).exists()

    def test_invite_success_email_failed_returns_failed_delivery(
        self, client, url, monkeypatch, settings
    ):
        """
        send_invite_email HTTPError fırlatır => message 'Davet oluşturuldu;
        e-posta gönderilemedi...' ve email_delivery 'failed'
        """
        from requests import HTTPError

        org = Organization.objects.create(
            name="Org",
            slug="org",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        settings.FRONTEND_BASE_URL = "http://frontend.test"

        def fake_send_invite_email(to_email, invite_link, org_name):
            raise HTTPError("mailgun down")

        monkeypatch.setattr("core.views.send_invite_email", fake_send_invite_email)

        res = client.post(url, {"email": "invitee2@example.com"}, format="json")

        assert res.status_code == 201
        assert res.data["status"] == 201
        expected_message = (
            "Davet oluşturuldu; e-posta gönderilemedi. "
            "Davet linkini kopyalayıp paylaşın."
        )

        assert res.data["message"] == expected_message

        data = res.data["data"]
        assert data["email"] == "invitee2@example.com"
        assert data["email_delivery"] == "failed"
        assert data["invite_link"].startswith(
            "http://frontend.test/accept-invite?token="
        )

        assert Invitation.objects.filter(
            email="invitee2@example.com", organization=org
        ).exists()


@pytest.mark.django_db
class TestAcceptInviteAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        # reverse patlarsa: return "/api/core/orgs/accept/invite/"
        return reverse("org-accept-invite")

    def create_org(self, name="Org", slug="org"):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
            owner_email="owner@example.com",
        )

    def create_invite(
        self,
        org,
        email="invitee@example.com",
        is_used=False,
        expires_at=None,
        token=None,
    ):
        return Invitation.objects.create(
            organization=org,
            email=email,
            token=token or uuid.uuid4(),
            is_used=is_used,
            expires_at=expires_at or (timezone.now() + timedelta(days=1)),
        )

    def test_accept_invite_success_creates_user_and_marks_invite_used(
        self, client, url
    ):
        org = self.create_org()
        invite = self.create_invite(org, email="invitee@example.com")

        payload = {
            "token": str(invite.token),
            "username": "invitee",
            "email": "invitee@example.com",
            "password": "StrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 201
        assert res.data["status"] == 201
        assert res.data["message"] == "Davet kabul edildi, kayıt tamamlandı."
        assert res.data["data"]["username"] == "invitee"
        assert res.data["data"]["email"] == "invitee@example.com"

        user = Users.objects.get(email__iexact="invitee@example.com")
        assert user.organization_id == org.id
        assert user.user_type == 2
        assert user.is_active is True
        assert user.is_deleted is False
        assert user.check_password("StrongPass123!") is True

        invite.refresh_from_db()
        assert invite.is_used is True

    def test_accept_invite_invalid_token(self, client, url):
        payload = {
            "token": str(uuid.uuid4()),
            "username": "x",
            "email": "x@example.com",
            "password": "StrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "token" in res.data

    def test_accept_invite_already_used(self, client, url):
        org = self.create_org()
        invite = self.create_invite(org, email="invitee@example.com", is_used=True)

        payload = {
            "token": str(invite.token),
            "username": "invitee",
            "email": "invitee@example.com",
            "password": "StrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "token" in res.data

    def test_accept_invite_expired(self, client, url):
        org = self.create_org()
        invite = self.create_invite(
            org,
            email="invitee@example.com",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        payload = {
            "token": str(invite.token),
            "username": "invitee",
            "email": "invitee@example.com",
            "password": "StrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "token" in res.data

    def test_accept_invite_email_mismatch(self, client, url):
        org = self.create_org()
        invite = self.create_invite(org, email="invitee@example.com")

        payload = {
            "token": str(invite.token),
            "username": "invitee",
            "email": "other@example.com",
            "password": "StrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "email" in res.data

    def test_accept_invite_existing_user_other_org_raises(self, client, url):
        org1 = self.create_org(name="Org1", slug="org1")
        org2 = self.create_org(name="Org2", slug="org2")

        Users.objects.create_user(
            username="existing",
            email="invitee@example.com",
            password="StrongPass123!",
            organization=org2,
            user_type=2,
            is_active=True,
        )

        invite = self.create_invite(org1, email="invitee@example.com")

        payload = {
            "token": str(invite.token),
            "username": "existing",
            "email": "invitee@example.com",
            "password": "StrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert (
            "non_field_errors" in res.data
            or isinstance(res.data, list)
            or isinstance(res.data, str)
        )

    def test_accept_invite_existing_user_without_org_gets_assigned(self, client, url):
        org = self.create_org()
        invite = self.create_invite(org, email="invitee@example.com")

        user = Users.objects.create_user(
            username="existing",
            email="invitee@example.com",
            password="OldPass123!",
            organization=None,
            user_type=2,
            is_active=False,
            is_deleted=True,
        )

        payload = {
            "token": str(invite.token),
            "username": "existing",
            "email": "invitee@example.com",
            "password": "NewStrongPass123!",
        }
        res = client.post(url, payload, format="json")

        assert res.status_code == 201

        user.refresh_from_db()
        assert user.organization_id == org.id
        assert user.user_type == 2
        assert user.is_active is True
        assert user.is_deleted is False
        assert user.check_password("NewStrongPass123!") is True

        invite.refresh_from_db()
        assert invite.is_used is True


@pytest.mark.django_db
class TestOrganizationMembersListAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-members-list")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_org_members_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_org_members_forbidden_for_non_admin(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )
        member = Users.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, member)

        res = client.get(url)
        assert res.status_code == 403

    def test_org_members_org_not_found_returns_empty_list(self, client, url):
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, admin)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Organization bulunamadı."
        assert res.data["data"] == []

    def test_org_members_org_deleted_returns_empty_list(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=True,
        )
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, admin)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Organization bulunamadı."
        assert res.data["data"] == []

    def test_list_members_paginated_ordered(self, client, url):
        org = Organization.objects.create(
            name="Org",
            slug="org",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )

        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
            is_deleted=False,
        )

        u1 = Users.objects.create_user(
            username="u1",
            email="u1@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
            is_deleted=False,
        )
        u2 = Users.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=3,
            is_active=True,
            is_deleted=False,
        )

        Users.objects.create_user(
            username="deleted",
            email="deleted@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
            is_deleted=True,
        )

        self.auth(client, admin)

        res = client.get(url)

        assert res.status_code == 200

        assert "results" in res.data
        results = res.data["results"]

        returned_ids = [item["id"] for item in results]
        assert admin.id in returned_ids
        assert u1.id in returned_ids
        assert u2.id in returned_ids

        assert Users.objects.filter(username="deleted").first().id not in returned_ids

        assert results[0]["id"] == u2.id


@pytest.mark.django_db
class TestOrganizationMemberRoleUpdateAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def url(self, user_id: int) -> str:
        return reverse("org-member-role-update", kwargs={"id": user_id})

    @pytest.fixture
    def org1(self):
        return Organization.objects.create(
            name="Org1",
            slug="org1",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )

    @pytest.fixture
    def org2(self):
        return Organization.objects.create(
            name="Org2",
            slug="org2",
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )

    @pytest.fixture
    def admin1(self, org1):
        return Users.objects.create_user(
            username="admin1",
            email="admin1@example.com",
            password="StrongPass123!",
            organization=org1,
            user_type=1,
            is_active=True,
            is_deleted=False,
        )

    @pytest.fixture
    def member1(self, org1):
        return Users.objects.create_user(
            username="member1",
            email="member1@example.com",
            password="StrongPass123!",
            organization=org1,
            user_type=2,
            is_active=True,
            is_deleted=False,
        )

    @pytest.fixture
    def admin2(self, org2):
        return Users.objects.create_user(
            username="admin2",
            email="admin2@example.com",
            password="StrongPass123!",
            organization=org2,
            user_type=1,
            is_active=True,
            is_deleted=False,
        )

    @pytest.fixture
    def member2(self, org2):
        return Users.objects.create_user(
            username="member2",
            email="member2@example.com",
            password="StrongPass123!",
            organization=org2,
            user_type=2,
            is_active=True,
            is_deleted=False,
        )

    def test_requires_auth(self, client, member1):
        res = client.patch(self.url(member1.id), {"user_type": 1}, format="json")
        assert res.status_code == 401

    def test_forbidden_for_non_admin(self, client, member1, org1):
        non_admin = Users.objects.create_user(
            username="x",
            email="x@example.com",
            password="StrongPass123!",
            organization=org1,
            user_type=2,
            is_active=True,
        )
        self.auth(client, non_admin)

        res = client.patch(self.url(member1.id), {"user_type": 1}, format="json")
        assert res.status_code == 403

    def test_target_user_not_found_returns_404(self, client, admin1):
        self.auth(client, admin1)

        res = client.patch(self.url(999999), {"user_type": 1}, format="json")
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Kullanıcı bulunamadı."

    def test_target_user_deleted_returns_404(self, client, admin1, org1):
        deleted_user = Users.objects.create_user(
            username="deleted",
            email="deleted@example.com",
            password="StrongPass123!",
            organization=org1,
            user_type=2,
            is_active=True,
            is_deleted=True,
        )
        self.auth(client, admin1)

        res = client.patch(self.url(deleted_user.id), {"user_type": 1}, format="json")
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Kullanıcı bulunamadı."

    def test_cannot_manage_user_from_other_org(self, client, admin1, member2):
        self.auth(client, admin1)

        res = client.patch(self.url(member2.id), {"user_type": 1}, format="json")
        assert res.status_code == 400
        assert "non_field_errors" in res.data

    def test_cannot_change_own_role(self, client, admin1):
        self.auth(client, admin1)

        res = client.patch(self.url(admin1.id), {"user_type": 1}, format="json")
        assert res.status_code == 400
        assert "non_field_errors" in res.data

    def test_empty_payload_returns_400(self, client, admin1, member1):
        self.auth(client, admin1)

        res = client.patch(self.url(member1.id), {}, format="json")
        assert res.status_code == 400
        assert "non_field_errors" in res.data

    def test_cannot_delete_admin_user(self, client, admin1, org1):
        other_admin = Users.objects.create_user(
            username="adminX",
            email="adminx@example.com",
            password="StrongPass123!",
            organization=org1,
            user_type=1,
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, admin1)

        res = client.patch(
            self.url(other_admin.id), {"is_deleted": True}, format="json"
        )
        assert res.status_code == 400
        assert "non_field_errors" in res.data

    def test_member_to_admin_success(self, client, admin1, member1):
        self.auth(client, admin1)

        res = client.patch(self.url(member1.id), {"user_type": 1}, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Üye admin yapıldı."

        member1.refresh_from_db()
        assert member1.user_type == 1

    def test_admin_to_member_not_allowed(self, client, admin1, org1):
        other_admin = Users.objects.create_user(
            username="adminX",
            email="adminx@example.com",
            password="StrongPass123!",
            organization=org1,
            user_type=1,
            is_active=True,
            is_deleted=False,
        )
        self.auth(client, admin1)

        res = client.patch(self.url(other_admin.id), {"user_type": 2}, format="json")
        assert res.status_code == 400
        assert "non_field_errors" in res.data

    def test_delete_member_success_unassigns_user(self, client, admin1, member1):
        self.auth(client, admin1)

        res = client.patch(self.url(member1.id), {"is_deleted": True}, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Üye silindi."

        member1.refresh_from_db()
        assert member1.is_deleted is True
        assert member1.is_active is False
        assert member1.organization is None
        assert member1.user_type == 2


@pytest.mark.django_db
class TestOrganizationInvitationsListAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-invitations-list")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_invite(self, org, invited_by, email, is_used, expires_at):
        return Invitation.objects.create(
            organization=org,
            invited_by=invited_by,
            email=email,
            is_used=is_used,
            expires_at=expires_at,
        )

    def test_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_forbidden_for_non_admin(self, client, url):
        org = self.create_org()
        member = Users.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
        )
        self.auth(client, member)

        res = client.get(url)
        assert res.status_code == 403

    def test_org_not_found_returns_404(self, client, url):
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        res = client.get(url)
        assert res.status_code == 404
        assert res.data["detail"] == "Organization bulunamadı."

    def test_org_deleted_returns_404(self, client, url):
        org = self.create_org(is_deleted=True)
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        res = client.get(url)
        assert res.status_code == 404
        assert res.data["detail"] == "Organization bulunamadı."

    def test_default_status_pending_filters_is_used_false(self, client, url):
        org = self.create_org()
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        now = timezone.now()
        inv_pending = self.create_invite(
            org,
            admin,
            "p@example.com",
            is_used=False,
            expires_at=now + timedelta(days=5),
        )
        self.create_invite(
            org,
            admin,
            "used@example.com",
            is_used=True,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url)
        assert res.status_code == 200
        assert "results" in res.data

        results = res.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == inv_pending.id
        assert results[0]["is_used"] is False

        assert results[0]["invited_by_username"] == "admin"
        assert results[0]["organization_name"] == org.name

    def test_status_used_filters_is_used_true(self, client, url):
        org = self.create_org()
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        now = timezone.now()
        self.create_invite(
            org,
            admin,
            "p@example.com",
            is_used=False,
            expires_at=now + timedelta(days=5),
        )
        inv_used = self.create_invite(
            org,
            admin,
            "u@example.com",
            is_used=True,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url + "?status=used")
        assert res.status_code == 200
        results = res.data["results"]

        assert len(results) == 1
        assert results[0]["id"] == inv_used.id
        assert results[0]["is_used"] is True

    def test_status_all_returns_all(self, client, url):
        org = self.create_org()
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        now = timezone.now()
        inv1 = self.create_invite(
            org,
            admin,
            "a@example.com",
            is_used=False,
            expires_at=now + timedelta(days=1),
        )
        inv2 = self.create_invite(
            org,
            admin,
            "b@example.com",
            is_used=True,
            expires_at=now + timedelta(days=2),
        )

        res = client.get(url + "?status=all")
        assert res.status_code == 200
        results = res.data["results"]

        returned_ids = [r["id"] for r in results]
        assert inv1.id in returned_ids
        assert inv2.id in returned_ids

    def test_invalid_status_returns_400(self, client, url):
        org = self.create_org()
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        res = client.get(url + "?status=wrong")
        assert res.status_code == 400
        assert res.data["detail"] == "Geçersiz status parametresi. pending|used|all"

    def test_orders_by_expires_at_desc(self, client, url):
        org = self.create_org()
        admin = Users.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )
        self.auth(client, admin)

        now = timezone.now()
        inv_early = self.create_invite(
            org,
            admin,
            "early@example.com",
            is_used=False,
            expires_at=now + timedelta(days=1),
        )
        inv_late = self.create_invite(
            org,
            admin,
            "late@example.com",
            is_used=False,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url)
        assert res.status_code == 200
        results = res.data["results"]

        assert len(results) == 2
        assert results[0]["id"] == inv_late.id
        assert results[1]["id"] == inv_early.id


@pytest.mark.django_db
class TestOrganizationInvitationsListAPISecond:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-invitations-list")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_invite(self, org, invited_by, email, is_used, expires_at):
        return Invitation.objects.create(
            organization=org,
            invited_by=invited_by,
            email=email,
            is_used=is_used,
            expires_at=expires_at,
        )

    def create_admin(self, org=None, username="admin", email="admin@example.com"):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )

    def create_member(self, org, username="member", email="member@example.com"):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
        )

    def test_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_forbidden_for_non_admin(self, client, url):
        org = self.create_org()
        member = self.create_member(org=org)
        self.auth(client, member)

        res = client.get(url)
        assert res.status_code == 403

    def test_org_not_found_returns_404(self, client, url):
        admin = self.create_admin(org=None)
        self.auth(client, admin)

        res = client.get(url)
        assert res.status_code == 404
        assert res.data["detail"] == "Organization bulunamadı."

    def test_org_deleted_returns_404(self, client, url):
        org = self.create_org(is_deleted=True)
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        res = client.get(url)
        assert res.status_code == 404
        assert res.data["detail"] == "Organization bulunamadı."

    def test_default_status_pending_filters_is_used_false(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        now = timezone.now()
        inv_pending = self.create_invite(
            org=org,
            invited_by=admin,
            email="p@example.com",
            is_used=False,
            expires_at=now + timedelta(days=5),
        )
        self.create_invite(
            org=org,
            invited_by=admin,
            email="used@example.com",
            is_used=True,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url)
        assert res.status_code == 200
        assert "results" in res.data

        results = res.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == inv_pending.id
        assert results[0]["is_used"] is False

        assert results[0]["invited_by_username"] == admin.username
        assert results[0]["organization_name"] == org.name

    def test_status_used_filters_is_used_true(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        now = timezone.now()
        self.create_invite(
            org,
            admin,
            "p@example.com",
            is_used=False,
            expires_at=now + timedelta(days=5),
        )
        inv_used = self.create_invite(
            org,
            admin,
            "u@example.com",
            is_used=True,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url + "?status=used")
        assert res.status_code == 200

        results = res.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == inv_used.id
        assert results[0]["is_used"] is True

    def test_status_all_returns_all(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        now = timezone.now()
        inv1 = self.create_invite(
            org,
            admin,
            "a@example.com",
            is_used=False,
            expires_at=now + timedelta(days=1),
        )
        inv2 = self.create_invite(
            org,
            admin,
            "b@example.com",
            is_used=True,
            expires_at=now + timedelta(days=2),
        )

        res = client.get(url + "?status=all")
        assert res.status_code == 200

        results = res.data["results"]
        returned_ids = [r["id"] for r in results]
        assert inv1.id in returned_ids
        assert inv2.id in returned_ids

    def test_invalid_status_returns_400(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        res = client.get(url + "?status=wrong")
        assert res.status_code == 400
        assert res.data["detail"] == "Geçersiz status parametresi. pending|used|all"

    def test_status_param_is_case_insensitive_and_stripped(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        now = timezone.now()
        inv_pending = self.create_invite(
            org,
            admin,
            "p@example.com",
            is_used=False,
            expires_at=now + timedelta(days=5),
        )
        self.create_invite(
            org,
            admin,
            "u@example.com",
            is_used=True,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url + "?status=  PENDING  ")
        assert res.status_code == 200

        results = res.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == inv_pending.id

    def test_orders_by_expires_at_desc(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        now = timezone.now()
        inv_early = self.create_invite(
            org,
            admin,
            "early@example.com",
            is_used=False,
            expires_at=now + timedelta(days=1),
        )
        inv_late = self.create_invite(
            org,
            admin,
            "late@example.com",
            is_used=False,
            expires_at=now + timedelta(days=10),
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]
        assert len(results) == 2
        assert results[0]["id"] == inv_late.id
        assert results[1]["id"] == inv_early.id

    def test_pagination_returns_10_results_and_next_link(self, client, url):
        """
        Pagination10 olduğu için 11 kayıt oluşturup:
        - count = 11
        - results len = 10
        - next dolu olmalı
        """
        org = self.create_org()
        admin = self.create_admin(org=org)
        self.auth(client, admin)

        now = timezone.now()

        for i in range(11):
            self.create_invite(
                org=org,
                invited_by=admin,
                email=f"user{i}@example.com",
                is_used=False,
                expires_at=now + timedelta(days=i),
            )

        res = client.get(url)
        assert res.status_code == 200

        assert res.data["count"] == 11
        assert len(res.data["results"]) == 10
        assert res.data["next"] is not None

        res2 = client.get(res.data["next"])
        assert res2.status_code == 200
        assert res2.data["count"] == 11
        assert len(res2.data["results"]) == 1
        assert res2.data["previous"] is not None


@pytest.mark.django_db
class TestProjectCreateAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("project-create")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_admin(self, org, username="admin", email="admin@example.com"):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )

    def create_member(self, org, username="member", email="member@example.com"):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=2,
            is_active=True,
        )

    def create_user(
        self, org, username, email, is_active=True, is_deleted=False, user_type=2
    ):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=user_type,
            is_active=is_active,
            is_deleted=is_deleted,
        )

    def payload(self, **overrides):
        """
        status değeri Projects.status choices'una göre uyarlanmalı.
        """
        data = {
            "name": "Project A",
            "description": "desc",
            "status": "active",
        }
        data.update(overrides)
        return data

    def test_requires_auth(self, client, url):
        res = client.post(url, data=self.payload(), format="json")
        assert res.status_code == 401

    def test_forbidden_for_non_admin(self, client, url):
        org = self.create_org()
        member = self.create_member(org)
        self.auth(client, member)

        res = client.post(url, data=self.payload(), format="json")
        assert res.status_code == 403

    def test_validation_error_when_name_missing(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org)
        self.auth(client, admin)

        res = client.post(url, data=self.payload(name=None), format="json")
        assert res.status_code == 400
        assert "name" in res.data

    def test_appointed_person_must_be_in_same_org(self, client, url):
        org1 = self.create_org(name="Org1", slug="org1")
        org2 = self.create_org(name="Org2", slug="org2")

        admin = self.create_admin(org1)
        other_org_user = self.create_user(
            org2, username="u2", email="u2@example.com", user_type=2
        )

        self.auth(client, admin)

        res = client.post(
            url,
            data=self.payload(appointed_person=other_org_user.id),
            format="json",
        )
        assert res.status_code == 400
        assert "appointed_person" in res.data
        assert (
            res.data["appointed_person"][0]
            == "Atanan kişi aynı organization içinde olmalı."
        )

    def test_create_project_without_appointed_person(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org)
        self.auth(client, admin)

        res = client.post(url, data=self.payload(appointed_person=None), format="json")
        assert res.status_code == 201
        assert res.data["status"] == 201
        assert res.data["message"] == "Project oluşturuldu."
        assert "data" in res.data
        assert res.data["data"]["name"] == "Project A"

        project_id = res.data["data"]["id"]
        p = Projects.objects.get(id=project_id)

        assert p.organization_id == org.id
        assert p.created_by_id == admin.id
        assert p.appointed_person_id is None

    def test_create_project_with_appointed_person_in_same_org(self, client, url):
        org = self.create_org()
        admin = self.create_admin(org)
        appointed = self.create_user(
            org, username="dev1", email="dev1@example.com", user_type=2
        )

        self.auth(client, admin)

        res = client.post(
            url,
            data=self.payload(appointed_person=appointed.id),
            format="json",
        )
        assert res.status_code == 201

        project_id = res.data["data"]["id"]
        p = Projects.objects.get(id=project_id)

        assert p.organization_id == org.id
        assert p.created_by_id == admin.id
        assert p.appointed_person_id == appointed.id

        assert res.data["data"]["appointed_person"] == appointed.id

    def test_appointed_person_must_be_active_and_not_deleted(self, client, url):
        """
        appointed_person field queryset:
        Users.objects.filter(is_deleted=False, is_active=True)
        Bu yüzden:
        - is_active=False veya is_deleted=True user seçilirse DRF
        'Invalid pk' döndürmeli.
        """
        org = self.create_org()
        admin = self.create_admin(org)

        inactive_user = self.create_user(
            org,
            username="inactive",
            email="inactive@example.com",
            is_active=False,
            is_deleted=False,
        )
        deleted_user = self.create_user(
            org,
            username="deleted",
            email="deleted@example.com",
            is_active=True,
            is_deleted=True,
        )

        self.auth(client, admin)

        res1 = client.post(
            url, data=self.payload(appointed_person=inactive_user.id), format="json"
        )
        assert res1.status_code == 400
        assert "appointed_person" in res1.data

        res2 = client.post(
            url, data=self.payload(appointed_person=deleted_user.id), format="json"
        )
        assert res2.status_code == 400
        assert "appointed_person" in res2.data


@pytest.mark.django_db
class TestOrganizationUsersAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-users-list")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_user(
        self,
        *,
        org=None,
        username,
        email,
        user_type=2,
        is_active=True,
        is_deleted=False,
        first_name="",
        last_name="",
        date_joined=None,
    ):
        """
        Users.create_user date_joined genelde auto_now_add gibi çalışır.
        Testte sıralama için date_joined'ı sonradan update ediyoruz.
        """
        user = Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=user_type,
            is_active=is_active,
            is_deleted=is_deleted,
            first_name=first_name,
            last_name=last_name,
        )
        if date_joined is not None:
            Users.objects.filter(id=user.id).update(date_joined=date_joined)
            user.refresh_from_db()
        return user

    def test_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_returns_400_if_user_has_no_organization(self, client, url):
        admin = self.create_user(
            org=None,
            username="admin",
            email="admin@example.com",
            user_type=1,
        )
        self.auth(client, admin)

        res = client.get(url)
        assert res.status_code == 400
        assert res.data["status"] == 400
        assert res.data["message"] == "Kullanıcıya bağlı bir organization bulunamadı."

    def test_returns_403_if_user_not_admin_user_type_1(self, client, url):
        org = self.create_org()
        member = self.create_user(
            org=org,
            username="member",
            email="member@example.com",
            user_type=2,
        )
        self.auth(client, member)

        res = client.get(url)
        assert res.status_code == 403

        assert "detail" in res.data

    def test_lists_only_active_not_deleted_users_in_same_org(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        u1 = self.create_user(
            org=org,
            username="u1",
            email="u1@example.com",
            user_type=2,
            is_active=True,
            is_deleted=False,
        )

        self.create_user(
            org=org,
            username="inactive",
            email="inactive@example.com",
            user_type=2,
            is_active=False,
            is_deleted=False,
        )

        self.create_user(
            org=org,
            username="deleted",
            email="deleted@example.com",
            user_type=2,
            is_active=True,
            is_deleted=True,
        )

        org2 = self.create_org(name="Org2", slug="org2")
        self.create_user(
            org=org2,
            username="other",
            email="other@example.com",
            user_type=2,
            is_active=True,
            is_deleted=False,
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]
        returned_ids = [r["id"] for r in results]

        assert admin.id in returned_ids
        assert u1.id in returned_ids

        assert len(results) == 2

        row = next(r for r in results if r["id"] == admin.id)
        assert set(row.keys()) == {
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "user_type",
            "date_joined",
        }

    def test_orders_by_date_joined_desc(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        now = timezone.now()
        u_old = self.create_user(
            org=org,
            username="old",
            email="old@example.com",
            date_joined=now - timedelta(days=5),
        )
        u_new = self.create_user(
            org=org,
            username="new",
            email="new@example.com",
            date_joined=now - timedelta(days=1),
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]

        Users.objects.filter(id=admin.id).update(date_joined=now - timedelta(days=10))
        res = client.get(url)
        results = res.data["results"]

        assert results[0]["id"] == u_new.id
        assert results[1]["id"] == u_old.id
        assert results[2]["id"] == admin.id

    def test_pagination_returns_10_results_and_next_link(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        now = timezone.now()

        for i in range(11):
            self.create_user(
                org=org,
                username=f"user{i}",
                email=f"user{i}@example.com",
                user_type=2,
                is_active=True,
                is_deleted=False,
                date_joined=now + timedelta(minutes=i),
            )

        res = client.get(url)
        assert res.status_code == 200

        assert res.data["count"] == 12
        assert len(res.data["results"]) == 10
        assert res.data["next"] is not None

        res2 = client.get(res.data["next"])
        assert res2.status_code == 200
        assert res2.data["count"] == 12
        assert len(res2.data["results"]) == 2
        assert res2.data["previous"] is not None


@pytest.mark.django_db
class TestProjectListAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-project-list")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_user(
        self,
        *,
        org=None,
        username,
        email,
        user_type=2,
        is_active=True,
        is_deleted=False,
        first_name="",
        last_name="",
    ):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=user_type,
            is_active=is_active,
            is_deleted=is_deleted,
            first_name=first_name,
            last_name=last_name,
        )

    def create_project(
        self,
        *,
        org,
        created_by,
        name,
        status="active",
        is_deleted=False,
        appointed_person=None,
        created_at=None,
    ):
        p = Projects.objects.create(
            organization=org,
            created_by=created_by,
            name=name,
            description="desc",
            status=status,
            appointed_person=appointed_person,
            is_deleted=is_deleted,
        )
        if created_at is not None:
            Projects.objects.filter(id=p.id).update(created_at=created_at)
            p.refresh_from_db()
        return p

    def test_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_forbidden_for_non_admin(self, client, url):
        org = self.create_org()
        member = self.create_user(
            org=org, username="member", email="member@example.com", user_type=2
        )
        self.auth(client, member)

        res = client.get(url)
        assert res.status_code == 403
        assert "detail" in res.data

    def test_org_not_found_returns_404(self, client, url):
        admin = self.create_user(
            org=None, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        res = client.get(url)
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Organization bulunamadı."

    def test_lists_only_projects_in_same_org_and_not_deleted(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        org2 = self.create_org(name="Org2", slug="org2")
        admin2 = self.create_user(
            org=org2, username="admin2", email="admin2@example.com", user_type=1
        )

        p1 = self.create_project(org=org, created_by=admin, name="P1", is_deleted=False)
        self.create_project(
            org=org, created_by=admin, name="P_deleted", is_deleted=True
        )
        self.create_project(
            org=org2, created_by=admin2, name="P_other_org", is_deleted=False
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]
        returned_ids = [r["id"] for r in results]

        assert p1.id in returned_ids
        assert len(results) == 1

        row = results[0]
        assert set(row.keys()) == {
            "id",
            "name",
            "description",
            "status",
            "appointed_person",
            "created_at",
            "updated_at",
        }

    def test_orders_by_created_at_desc(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        now = timezone.now()
        p_old = self.create_project(
            org=org, created_by=admin, name="Old", created_at=now - timedelta(days=5)
        )
        p_new = self.create_project(
            org=org, created_by=admin, name="New", created_at=now - timedelta(days=1)
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]
        assert len(results) == 2
        assert results[0]["id"] == p_new.id
        assert results[1]["id"] == p_old.id

    def test_serializer_appointed_person_returns_none_when_missing(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        self.create_project(org=org, created_by=admin, name="P1", appointed_person=None)

        res = client.get(url)
        assert res.status_code == 200
        results = res.data["results"]
        assert len(results) == 1
        assert results[0]["appointed_person"] is None

    def test_serializer_appointed_person_returns_dict_when_present(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        appointed = self.create_user(
            org=org,
            username="dev1",
            email="dev1@example.com",
            user_type=2,
            first_name="Dev",
            last_name="One",
        )
        self.auth(client, admin)

        self.create_project(
            org=org, created_by=admin, name="P1", appointed_person=appointed
        )

        res = client.get(url)
        assert res.status_code == 200
        results = res.data["results"]
        assert len(results) == 1

        ap = results[0]["appointed_person"]
        assert ap["id"] == appointed.id
        assert ap["first_name"] == appointed.first_name
        assert ap["last_name"] == appointed.last_name
        assert ap["email"] == appointed.email

    def test_pagination_returns_10_results_and_next_link(self, client, url):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        self.auth(client, admin)

        now = timezone.now()

        for i in range(11):
            self.create_project(
                org=org,
                created_by=admin,
                name=f"P{i}",
                created_at=now + timedelta(minutes=i),
                is_deleted=False,
            )

        res = client.get(url)
        assert res.status_code == 200

        assert res.data["count"] == 11
        assert len(res.data["results"]) == 10
        assert res.data["next"] is not None

        res2 = client.get(res.data["next"])
        assert res2.status_code == 200
        assert res2.data["count"] == 11
        assert len(res2.data["results"]) == 1
        assert res2.data["previous"] is not None


@pytest.mark.django_db
class TestMyAppointedProjectsAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("org-my-project-list")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_user(
        self,
        *,
        org=None,
        username,
        email,
        user_type=2,
        is_active=True,
        is_deleted=False,
        first_name="",
        last_name="",
    ):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=user_type,
            is_active=is_active,
            is_deleted=is_deleted,
            first_name=first_name,
            last_name=last_name,
        )

    def create_project(
        self,
        *,
        org,
        created_by,
        name,
        status="active",
        is_deleted=False,
        appointed_person=None,
        created_at=None,
    ):
        p = Projects.objects.create(
            organization=org,
            created_by=created_by,
            name=name,
            description="desc",
            status=status,
            appointed_person=appointed_person,
            is_deleted=is_deleted,
        )
        if created_at is not None:
            Projects.objects.filter(id=p.id).update(created_at=created_at)
            p.refresh_from_db()
        return p

    def test_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_org_not_found_returns_404(self, client, url):
        user = self.create_user(
            org=None, username="u1", email="u1@example.com", user_type=2
        )
        self.auth(client, user)

        res = client.get(url)
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Organization bulunamadı."

    def test_returns_only_projects_where_user_is_appointed_person(self, client, url):
        org = self.create_org()
        me = self.create_user(
            org=org,
            username="me",
            email="me@example.com",
            first_name="Mete",
            last_name="Yildirim",
            user_type=2,
        )
        creator = self.create_user(
            org=org, username="creator", email="creator@example.com", user_type=1
        )

        self.auth(client, me)

        p1 = self.create_project(
            org=org,
            created_by=creator,
            name="P1",
            appointed_person=me,
            is_deleted=False,
        )

        other = self.create_user(org=org, username="other", email="other@example.com")
        self.create_project(
            org=org,
            created_by=creator,
            name="P_other",
            appointed_person=other,
            is_deleted=False,
        )

        self.create_project(
            org=org,
            created_by=creator,
            name="P_deleted",
            appointed_person=me,
            is_deleted=True,
        )

        org2 = self.create_org(name="Org2", slug="org2")
        creator2 = self.create_user(
            org=org2, username="creator2", email="creator2@example.com", user_type=1
        )
        self.create_project(
            org=org2,
            created_by=creator2,
            name="P_other_org",
            appointed_person=me,
            is_deleted=False,
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == p1.id

        ap = results[0]["appointed_person"]
        assert ap["id"] == me.id
        assert ap["first_name"] == me.first_name
        assert ap["last_name"] == me.last_name
        assert ap["email"] == me.email

    def test_orders_by_created_at_desc(self, client, url):
        org = self.create_org()
        me = self.create_user(
            org=org, username="me", email="me@example.com", user_type=2
        )
        creator = self.create_user(
            org=org, username="creator", email="creator@example.com", user_type=1
        )

        self.auth(client, me)

        now = timezone.now()
        p_old = self.create_project(
            org=org,
            created_by=creator,
            name="Old",
            appointed_person=me,
            created_at=now - timedelta(days=5),
        )
        p_new = self.create_project(
            org=org,
            created_by=creator,
            name="New",
            appointed_person=me,
            created_at=now - timedelta(days=1),
        )

        res = client.get(url)
        assert res.status_code == 200

        results = res.data["results"]
        assert len(results) == 2
        assert results[0]["id"] == p_new.id
        assert results[1]["id"] == p_old.id

    def test_pagination_returns_10_results_and_next_link(self, client, url):
        org = self.create_org()
        me = self.create_user(
            org=org, username="me", email="me@example.com", user_type=2
        )
        creator = self.create_user(
            org=org, username="creator", email="creator@example.com", user_type=1
        )

        self.auth(client, me)

        now = timezone.now()
        for i in range(11):
            self.create_project(
                org=org,
                created_by=creator,
                name=f"P{i}",
                appointed_person=me,
                created_at=now + timedelta(minutes=i),
                is_deleted=False,
            )

        res = client.get(url)
        assert res.status_code == 200

        assert res.data["count"] == 11
        assert len(res.data["results"]) == 10
        assert res.data["next"] is not None

        res2 = client.get(res.data["next"])
        assert res2.status_code == 200
        assert res2.data["count"] == 11
        assert len(res2.data["results"]) == 1
        assert res2.data["previous"] is not None


@pytest.mark.django_db
class TestProjectUpdateAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    def url(self, project_id):
        return reverse("org-project-update", kwargs={"id": project_id})

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_user(
        self,
        *,
        org=None,
        username,
        email,
        user_type=2,
        is_active=True,
        is_deleted=False,
        first_name="",
        last_name="",
    ):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=user_type,
            is_active=is_active,
            is_deleted=is_deleted,
            first_name=first_name,
            last_name=last_name,
        )

    def create_project(
        self,
        *,
        org,
        created_by,
        name="P1",
        description="desc",
        status="active",
        appointed_person=None,
        is_deleted=False,
    ):
        return Projects.objects.create(
            organization=org,
            created_by=created_by,
            name=name,
            description=description,
            status=status,
            appointed_person=appointed_person,
            is_deleted=is_deleted,
        )

    def test_requires_auth(self, client):
        res = client.patch(self.url(1), data={"name": "X"}, format="json")
        assert res.status_code == 401

    def test_org_not_found_returns_404(self, client):
        user = self.create_user(
            org=None, username="u1", email="u1@example.com", user_type=2
        )
        self.auth(client, user)

        res = client.patch(self.url(1), data={"name": "X"}, format="json")
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Organization bulunamadı."

    def test_project_not_found_returns_404_when_not_in_org(self, client):
        org1 = self.create_org(name="Org1", slug="org1")
        org2 = self.create_org(name="Org2", slug="org2")

        admin1 = self.create_user(
            org=org1, username="admin1", email="admin1@example.com", user_type=1
        )
        admin2 = self.create_user(
            org=org2, username="admin2", email="admin2@example.com", user_type=1
        )

        project_org2 = self.create_project(org=org2, created_by=admin2, name="P2")

        self.auth(client, admin1)

        res = client.patch(self.url(project_org2.id), data={"name": "X"}, format="json")
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Project bulunamadı."

    def test_project_not_found_returns_404_when_deleted(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        project = self.create_project(org=org, created_by=admin, is_deleted=True)

        self.auth(client, admin)

        res = client.patch(self.url(project.id), data={"name": "X"}, format="json")
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Project bulunamadı."

    def test_forbidden_if_not_admin_tester_or_appointed(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        project = self.create_project(org=org, created_by=admin)

        outsider = self.create_user(
            org=org, username="outsider", email="outsider@example.com", user_type=2
        )
        self.auth(client, outsider)

        res = client.patch(self.url(project.id), data={"name": "Nope"}, format="json")
        assert res.status_code == 403
        assert res.data["status"] == 403
        assert res.data["message"] == "Bu project için yetkin yok."

    def test_admin_can_update_project(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        project = self.create_project(org=org, created_by=admin, name="Old Name")

        self.auth(client, admin)

        res = client.patch(
            self.url(project.id), data={"name": "New Name"}, format="json"
        )
        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Project güncellendi."
        assert res.data["data"]["name"] == "New Name"

        project.refresh_from_db()
        assert project.name == "New Name"

    def test_tester_can_update_project(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        tester = self.create_user(
            org=org, username="tester", email="tester@example.com", user_type=3
        )
        project = self.create_project(org=org, created_by=admin, name="Old Name")

        self.auth(client, tester)

        res = client.patch(
            self.url(project.id), data={"description": "Updated"}, format="json"
        )
        assert res.status_code == 200
        assert res.data["data"]["description"] == "Updated"

        project.refresh_from_db()
        assert project.description == "Updated"

    def test_appointed_user_can_update_project(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        appointed = self.create_user(
            org=org,
            username="dev1",
            email="dev1@example.com",
            user_type=2,
            first_name="Dev",
            last_name="One",
        )
        project = self.create_project(
            org=org, created_by=admin, appointed_person=appointed, name="Old"
        )

        self.auth(client, appointed)

        res = client.patch(
            self.url(project.id), data={"name": "Appointed Updated"}, format="json"
        )
        assert res.status_code == 200
        assert res.data["data"]["name"] == "Appointed Updated"

        ap = res.data["data"]["appointed_person"]
        assert ap["id"] == appointed.id
        assert ap["first_name"] == appointed.first_name
        assert ap["last_name"] == appointed.last_name
        assert ap["email"] == appointed.email

        project.refresh_from_db()
        assert project.name == "Appointed Updated"

    def test_returns_400_with_errors_on_validation_error(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        project = self.create_project(org=org, created_by=admin)

        self.auth(client, admin)

        res = client.patch(
            self.url(project.id), data={"status": "invalid_status"}, format="json"
        )
        assert res.status_code == 400
        assert res.data["status"] == 400
        assert res.data["message"] == "Validation error."
        assert "errors" in res.data
        assert "status" in res.data["errors"]


@pytest.mark.django_db
class TestProjectDetailAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    def url(self, project_id):
        return reverse("org-project-detail", kwargs={"id": project_id})

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def create_org(self, name="Org", slug="org", is_deleted=False):
        return Organization.objects.create(
            name=name,
            slug=slug,
            plan="free",
            max_users=10,
            is_active=True,
            is_deleted=is_deleted,
            owner_email="owner@example.com",
        )

    def create_user(
        self,
        *,
        org=None,
        username,
        email,
        user_type=2,
        is_active=True,
        is_deleted=False,
        first_name="",
        last_name="",
    ):
        return Users.objects.create_user(
            username=username,
            email=email,
            password="StrongPass123!",
            organization=org,
            user_type=user_type,
            is_active=is_active,
            is_deleted=is_deleted,
            first_name=first_name,
            last_name=last_name,
        )

    def create_project(
        self,
        *,
        org,
        created_by,
        name="P1",
        description="desc",
        status="active",
        appointed_person=None,
        is_deleted=False,
    ):
        return Projects.objects.create(
            organization=org,
            created_by=created_by,
            name=name,
            description=description,
            status=status,
            appointed_person=appointed_person,
            is_deleted=is_deleted,
        )

    def test_requires_auth(self, client):
        res = client.get(self.url(1))
        assert res.status_code == 401

    def test_org_not_found_returns_404(self, client):
        user = self.create_user(org=None, username="u1", email="u1@example.com")
        self.auth(client, user)

        res = client.get(self.url(1))
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Organization bulunamadı."

    def test_project_not_found_returns_404_when_not_in_org(self, client):
        org1 = self.create_org(name="Org1", slug="org1")
        org2 = self.create_org(name="Org2", slug="org2")

        user1 = self.create_user(org=org1, username="u1", email="u1@example.com")
        admin2 = self.create_user(
            org=org2, username="admin2", email="admin2@example.com", user_type=1
        )

        project_org2 = self.create_project(org=org2, created_by=admin2)

        self.auth(client, user1)

        res = client.get(self.url(project_org2.id))
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Project bulunamadı."

    def test_project_not_found_returns_404_when_deleted(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        project = self.create_project(org=org, created_by=admin, is_deleted=True)

        self.auth(client, admin)

        res = client.get(self.url(project.id))
        assert res.status_code == 404
        assert res.data["status"] == 404
        assert res.data["message"] == "Project bulunamadı."

    def test_returns_200_with_project_detail_and_appointed_person_none(self, client):
        org = self.create_org()
        user = self.create_user(org=org, username="u1", email="u1@example.com")
        project = self.create_project(org=org, created_by=user, appointed_person=None)

        self.auth(client, user)

        res = client.get(self.url(project.id))
        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Project detayı getirildi."
        assert "data" in res.data

        data = res.data["data"]
        assert data["id"] == project.id
        assert data["appointed_person"] is None

        assert set(data.keys()) == {
            "id",
            "name",
            "description",
            "status",
            "appointed_person",
            "created_at",
            "updated_at",
        }

    def test_returns_200_with_project_detail_and_appointed_person_dict(self, client):
        org = self.create_org()
        admin = self.create_user(
            org=org, username="admin", email="admin@example.com", user_type=1
        )
        appointed = self.create_user(
            org=org,
            username="dev1",
            email="dev1@example.com",
            first_name="Dev",
            last_name="One",
        )
        project = self.create_project(
            org=org, created_by=admin, appointed_person=appointed
        )

        self.auth(client, admin)

        res = client.get(self.url(project.id))
        assert res.status_code == 200

        data = res.data["data"]
        ap = data["appointed_person"]
        assert ap["id"] == appointed.id
        assert ap["first_name"] == appointed.first_name
        assert ap["last_name"] == appointed.last_name
        assert ap["email"] == appointed.email
