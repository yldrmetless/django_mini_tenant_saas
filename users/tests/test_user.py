import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import Organization
from users.models import Users


@pytest.mark.django_db
class TestRegisterAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("register")

    def test_register_success(self, client, url):
        payload = {
            "username": "mete",
            "email": "mete@example.com",
            "first_name": "Metehan",
            "last_name": "Yildirim",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        }

        res = client.post(url, payload, format="json")

        assert res.status_code == 201
        assert res.data["status"] == 201
        assert res.data["message"] == "Registration successful."

        created_id = res.data["data"]["id"]
        user = Users.objects.get(id=created_id)

        assert user.username == "mete"
        assert user.email == "mete@example.com"
        assert user.user_type == 2
        assert user.organization is None

        assert user.check_password("StrongPass123!") is True
        assert user.password != "StrongPass123!"

    def test_register_duplicate_email(self, client, url):
        Users.objects.create_user(
            username="u1",
            email="mete@example.com",
            password="StrongPass123!",
        )

        payload = {
            "username": "mete2",
            "email": "mete@example.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        }

        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "email" in res.data

    def test_register_duplicate_username(self, client, url):
        Users.objects.create_user(
            username="mete",
            email="x1@example.com",
            password="StrongPass123!",
        )

        payload = {
            "username": "mete",
            "email": "mete2@example.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        }

        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "username" in res.data

    def test_register_password_mismatch(self, client, url):
        payload = {
            "username": "mete3",
            "email": "mete3@example.com",
            "password": "StrongPass123!",
            "password2": "DifferentPass123!",
        }

        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "password2" in res.data


@pytest.mark.django_db
class TestLoginAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("login")

    def test_login_success_returns_tokens(self, client, url):
        Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="StrongPass123!",
            is_active=True,
            is_deleted=False,
            user_type=2,
        )

        payload = {"username": "mete", "password": "StrongPass123!"}
        res = client.post(url, payload, format="json")

        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Login successful."

        data = res.data["data"]
        assert "refresh" in data
        assert "access" in data
        assert "expire_time" in data

        assert isinstance(data["refresh"], str) and len(data["refresh"]) > 10
        assert isinstance(data["access"], str) and len(data["access"]) > 10
        assert isinstance(data["expire_time"], int)
        assert data["expire_time"] > 0

    def test_login_wrong_credentials(self, client, url):
        Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="StrongPass123!",
            is_active=True,
        )

        payload = {"username": "mete", "password": "WrongPass123!"}
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "non_field_errors" in res.data

    def test_login_inactive_user(self, client, url):
        Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="StrongPass123!",
            is_active=False,
        )

        payload = {"username": "mete", "password": "StrongPass123!"}
        res = client.post(url, payload, format="json")

        assert res.status_code == 400
        assert "non_field_errors" in res.data


@pytest.mark.django_db
class TestUpdateProfileAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("update_profile")

    @pytest.fixture
    def user(self):
        return Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="OldPass123!",
            first_name="Mete",
            last_name="Yildirim",
            is_active=True,
            is_deleted=False,
        )

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_update_profile_requires_auth(self, client, url):
        res = client.patch(url, {"first_name": "X"}, format="json")
        assert res.status_code == 401

    def test_update_profile_basic_fields(self, client, url, user):
        self.auth(client, user)

        payload = {
            "first_name": "Metehan",
            "last_name": "Yıldırım",
            "username": "mete_dev",
            "email": "mete.dev@example.com",
        }

        res = client.patch(url, payload, format="json")
        assert res.status_code == 200
        assert res.data["status"] == 200
        assert res.data["message"] == "Profile updated."

        user.refresh_from_db()
        assert user.first_name == "Metehan"
        assert user.last_name == "Yıldırım"
        assert user.username == "mete_dev"
        assert user.email == "mete.dev@example.com"

    def test_update_profile_duplicate_username(self, client, url, user):
        Users.objects.create_user(
            username="taken",
            email="taken@example.com",
            password="StrongPass123!",
        )

        self.auth(client, user)

        res = client.patch(url, {"username": "taken"}, format="json")
        assert res.status_code == 400
        assert "username" in res.data

    def test_update_profile_duplicate_email(self, client, url, user):
        Users.objects.create_user(
            username="x2",
            email="taken@example.com",
            password="StrongPass123!",
        )

        self.auth(client, user)

        res = client.patch(url, {"email": "taken@example.com"}, format="json")
        assert res.status_code == 400
        assert "email" in res.data

    def test_change_password_wrong_current_password(self, client, url, user):
        self.auth(client, user)

        payload = {
            "current_password": "WrongOldPass!",
            "new_password": "NewPass123!",
            "new_password2": "NewPass123!",
        }

        res = client.patch(url, payload, format="json")
        assert res.status_code == 400
        assert "non_field_errors" in res.data

        user.refresh_from_db()
        assert user.check_password("OldPass123!") is True

    def test_change_password_mismatch(self, client, url, user):
        self.auth(client, user)

        payload = {
            "current_password": "OldPass123!",
            "new_password": "NewPass123!",
            "new_password2": "DifferentPass123!",
        }

        res = client.patch(url, payload, format="json")
        assert res.status_code == 400
        assert "non_field_errors" in res.data

        user.refresh_from_db()
        assert user.check_password("OldPass123!") is True

    def test_change_password_success(self, client, url, user):
        self.auth(client, user)

        payload = {
            "current_password": "OldPass123!",
            "new_password": "NewPass123!",
            "new_password2": "NewPass123!",
        }

        res = client.patch(url, payload, format="json")
        assert res.status_code == 200
        assert res.data["status"] == 200

        user.refresh_from_db()
        assert user.check_password("NewPass123!") is True
        assert user.check_password("OldPass123!") is False


@pytest.mark.django_db
class TestUserMeAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("users-me")

    def auth(self, client, user):
        client.force_authenticate(user=user)

    def test_me_requires_auth(self, client, url):
        res = client.get(url)
        assert res.status_code == 401

    def test_me_returns_user_fields_and_org_none(self, client, url):
        user = Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="StrongPass123!",
            first_name="Mete",
            last_name="Yildirim",
            user_type=2,
            is_active=True,
            is_deleted=False,
        )

        self.auth(client, user)

        res = client.get(url)

        assert res.status_code == 200
        assert res.data["id"] == user.id
        assert res.data["username"] == "mete"
        assert res.data["email"] == "mete@example.com"
        assert res.data["first_name"] == "Mete"
        assert res.data["last_name"] == "Yildirim"
        assert res.data["user_type"] == 2
        assert res.data["is_active"] is True
        assert "date_joined" in res.data
        assert res.data["organization"] is None

    def test_me_returns_org_object_when_exists(self, client, url):
        org = Organization.objects.create(
            name="Acme",
            slug="acme",
            plan="starter",
            max_users=10,
            is_active=True,
            is_deleted=False,
        )
        user = Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="StrongPass123!",
            organization=org,
            user_type=1,
            is_active=True,
        )

        self.auth(client, user)

        res = client.get(url)

        assert res.status_code == 200
        org_data = res.data["organization"]
        assert org_data["id"] == org.id
        assert org_data["name"] == "Acme"
        assert org_data["slug"] == "acme"
        assert org_data["plan"] == "starter"
        assert org_data["max_users"] == 10
        assert org_data["is_active"] is True

    def test_me_org_deleted_returns_none(self, client, url):
        org = Organization.objects.create(
            name="DeletedOrg",
            slug="deleted-org",
            plan="starter",
            max_users=10,
            is_active=True,
            is_deleted=True,
        )
        user = Users.objects.create_user(
            username="mete",
            email="mete@example.com",
            password="StrongPass123!",
            organization=org,
            is_active=True,
        )

        self.auth(client, user)

        res = client.get(url)
        assert res.status_code == 200
        assert res.data["organization"] is None
