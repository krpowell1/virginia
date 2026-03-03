from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def user(db: None) -> User:
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def client() -> Client:
    """Return an unauthenticated test client."""
    return Client()


@pytest.fixture
def auth_client(user: User) -> Client:
    """Return an authenticated test client."""
    c = Client()
    c.login(username="testuser", password="testpass123")
    return c


class TestLogin:
    """Test the login page."""

    def test_login_page_renders(self, client: Client) -> None:
        """Login page loads successfully."""
        response = client.get("/accounts/login/")
        assert response.status_code == 200
        assert b"Sign in" in response.content

    def test_login_page_contains_face_id_elements(self, client: Client) -> None:
        """Login page includes WebAuthn placeholder and templates."""
        response = client.get("/accounts/login/")
        content = response.content.decode()
        assert "passkey-verification-placeholder" in content
        assert "passkey-verification-available-template" in content
        assert "passkey-verification-unavailable-template" in content

    def test_login_page_contains_password_form(self, client: Client) -> None:
        """Login page has a standard password form as fallback."""
        response = client.get("/accounts/login/")
        content = response.content.decode()
        assert 'name="username"' in content
        assert 'name="password"' in content
        assert "Sign in" in content

    def test_login_page_contains_webauthn_scripts(self, client: Client) -> None:
        """Login page loads the otp_webauthn auth scripts."""
        response = client.get("/accounts/login/")
        content = response.content.decode()
        assert "otp_webauthn_config" in content

    def test_login_success_redirects(self, client: Client, user: User) -> None:
        """Successful login redirects to dashboard."""
        response = client.post(
            "/accounts/login/",
            {"username": "testuser", "password": "testpass123"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_login_failure_shows_error(self, client: Client, user: User) -> None:
        """Failed login shows error message."""
        response = client.post(
            "/accounts/login/",
            {"username": "testuser", "password": "wrongpassword"},
        )
        assert response.status_code == 200
        assert b"Invalid username or password" in response.content


class TestLogout:
    """Test the logout flow."""

    def test_logout_redirects(self, auth_client: Client) -> None:
        """Logout redirects to login page."""
        response = auth_client.post("/accounts/logout/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


class TestRegisterPasskey:
    """Test the passkey registration page."""

    def test_requires_login(self, client: Client) -> None:
        """Passkey registration requires authentication."""
        response = client.get("/accounts/register-passkey/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_renders_for_authenticated_user(self, auth_client: Client) -> None:
        """Passkey registration page renders for logged-in user."""
        response = auth_client.get("/accounts/register-passkey/")
        assert response.status_code == 200
        assert b"Face ID" in response.content

    def test_contains_registration_elements(self, auth_client: Client) -> None:
        """Page includes WebAuthn registration placeholder and templates."""
        response = auth_client.get("/accounts/register-passkey/")
        content = response.content.decode()
        assert "passkey-registration-placeholder" in content
        assert "passkey-registration-available-template" in content
        assert "passkey-registration-unavailable-template" in content

    def test_contains_webauthn_register_scripts(self, auth_client: Client) -> None:
        """Page loads the otp_webauthn registration scripts."""
        response = auth_client.get("/accounts/register-passkey/")
        content = response.content.decode()
        assert "otp_webauthn_config" in content

    def test_contains_skip_link(self, auth_client: Client) -> None:
        """Page has a 'Skip for now' link to dashboard."""
        response = auth_client.get("/accounts/register-passkey/")
        assert b"Skip for now" in response.content
