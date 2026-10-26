from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from users.models import UserProfile
from .test_peer_review_allocation import make_user


class AccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.main = make_user("mainuser")
        self.main.email = "main@example.com"
        self.main.save()
        self.main.profile.qqid = "1234567"
        self.main.profile.save()
        self.payload = {
            "username": "alternate",
            "password": "some-random-pass908",
            "password_confirm": "some-random-pass908",
            "main_account_id": self.main.pk,
            "main_password": "long-password-902",
        }

    def test_verified_alias_inherits_contacts_not_permissions(self):
        self.main.is_staff = True
        self.main.save()
        response = self.client.post("/api/users/register/", self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        user = get_user_model().objects.get(username="alternate")
        self.assertEqual(user.profile.main_account, self.main)
        self.assertIsNone(user.profile.qqid)
        self.assertFalse(user.is_staff)
        self.assertEqual(response.data["user"]["email"], self.main.email)
        self.assertEqual(response.data["user"]["qqid"], "1234567")

    def test_invalid_main_password_and_chained_binding_rejected(self):
        self.assertEqual(
            self.client.post(
                "/api/users/register/",
                {**self.payload, "main_password": "bad"},
                format="json",
            ).status_code,
            400,
        )
        alias = make_user("existingalias", self.main)
        self.assertEqual(
            self.client.post(
                "/api/users/register/",
                {**self.payload, "main_account_id": alias.pk},
                format="json",
            ).status_code,
            400,
        )
        self.assertFalse(get_user_model().objects.filter(username="alternate").exists())

    def test_account_lookup_does_not_expose_contacts_or_linkage(self):
        make_user("mainalias", self.main)
        response = self.client.get("/api/users/accounts/?q=main")
        self.assertEqual(response.data, [{"id": self.main.pk, "username": "mainuser"}])

    def test_csrf_and_real_session_logout(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(
                "/api/users/login/",
                {"username": self.main.username, "password": "long-password-902"},
                format="json",
            ).status_code,
            403,
        )
        token = client.get("/api/users/csrf/").data["csrfToken"]
        response = client.post(
            "/api/users/login/",
            {"username": self.main.username, "password": "long-password-902"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200, response.data)
        token = client.get("/api/users/csrf/").data["csrfToken"]
        self.assertEqual(
            client.post(
                "/api/users/logout/", {}, format="json", HTTP_X_CSRFTOKEN=token
            ).status_code,
            200,
        )
        self.assertEqual(client.get("/api/users/me/").status_code, 403)

    def test_independent_registration_requires_contacts(self):
        self.assertEqual(
            self.client.post(
                "/api/users/register/",
                {
                    "username": "newuser",
                    "password": "random-long902",
                    "password_confirm": "random-long902",
                },
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(UserProfile.objects.count(), 1)
