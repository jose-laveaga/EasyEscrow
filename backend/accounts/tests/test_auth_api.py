from allauth.account.models import EmailAddress
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User


class AllauthApiTests(APITestCase):
    password = "StrongPass123!"

    def create_verified_user(self, email="verified@example.com", password=None):
        user = User.objects.create_user(
            email=email,
            password=password or self.password,
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )
        return user

    def login(self, email=None, password=None):
        return self.client.post(
            reverse("account_login"),
            {
                "login": email or "verified@example.com",
                "password": password or self.password,
            },
            format="json",
        )

    def test_login_endpoint_returns_rest_session_payload(self):
        user = self.create_verified_user()

        response = self.login(email=user.email)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Login successful.")
        self.assertEqual(response.data["redirect_to"], "/")
        self.assertTrue(response.data["session"]["is_authenticated"])
        self.assertEqual(response.data["session"]["user"]["email"], user.email)
        self.assertIn("authentication_methods", response.data["session"])

    def test_signup_and_confirm_email_flow_use_same_allauth_paths(self):
        signup_response = self.client.post(
            reverse("account_signup"),
            {
                "email": "pending@example.com",
                "first_name": "Jose",
                "middle_name": "Antonio",
                "last_name": "Martinez Lopez",
                "password1": self.password,
                "password2": self.password,
            },
            format="json",
        )

        self.assertEqual(signup_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            signup_response.data["redirect_to"],
            reverse("account_email_verification_sent"),
        )
        self.assertFalse(signup_response.data["session"]["is_authenticated"])
        self.assertEqual(
            signup_response.data["session"]["pending"]["id"],
            "email_verification",
        )

        code = self.client.session["account_email_verification_code"]["code"]

        pending_response = self.client.get(reverse("account_email_verification_sent"))
        self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            pending_response.data["verification"]["email"],
            "pending@example.com",
        )

        confirm_response = self.client.post(
            reverse("account_email_verification_sent"),
            {
                "action": "verify",
                "code": code,
            },
            format="json",
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertTrue(confirm_response.data["session"]["is_authenticated"])
        self.assertEqual(
            confirm_response.data["session"]["user"]["email"],
            "pending@example.com",
        )
        self.assertEqual(confirm_response.data["session"]["user"]["first_name"], "Jose")
        self.assertEqual(confirm_response.data["session"]["user"]["middle_name"], "Antonio")
        self.assertEqual(confirm_response.data["session"]["user"]["last_name"], "Martinez Lopez")

    def test_password_reset_flow_is_json_first(self):
        user = self.create_verified_user(email="reset@example.com")

        request_response = self.client.post(
            reverse("account_reset_password"),
            {"email": user.email},
            format="json",
        )

        self.assertEqual(request_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            request_response.data["redirect_to"],
            reverse("account_confirm_password_reset_code"),
        )

        code = self.client.session["account_password_reset_verification"]["code"]

        confirm_response = self.client.post(
            reverse("account_confirm_password_reset_code"),
            {"code": code},
            format="json",
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            confirm_response.data["redirect_to"],
            reverse("account_complete_password_reset"),
        )

        complete_response = self.client.post(
            reverse("account_complete_password_reset"),
            {
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            complete_response.data["redirect_to"],
            reverse("account_password_reset_completed"),
        )

        self.client.cookies.clear()
        login_response = self.login(
            email=user.email,
            password="NewStrongPass123!",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertTrue(login_response.data["session"]["is_authenticated"])

    def test_email_endpoint_lists_existing_addresses_and_adds_new_one(self):
        user = self.create_verified_user()
        login_response = self.login(email=user.email)
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        list_response = self.client.get(reverse("account_email"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["emails"][0]["email"], user.email)
        self.assertTrue(list_response.data["emails"][0]["primary"])

        add_response = self.client.post(
            reverse("account_email"),
            {
                "action": "add",
                "email": "secondary@example.com",
            },
            format="json",
        )

        self.assertEqual(add_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            add_response.data["redirect_to"],
            reverse("account_email_verification_sent"),
        )
        self.assertEqual(
            add_response.data["pending_verification"]["email"],
            "secondary@example.com",
        )
