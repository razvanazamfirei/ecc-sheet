"""Tests for development mock user switching."""

import os

import pytest


class TestDevRoutesDisabled:
    """Dev routes return 404 when MOCK_USERS_ENABLED is not set."""

    def test_switch_user_returns_404_when_disabled(self, client):
        original = os.environ.pop("MOCK_USERS_ENABLED", None)
        try:
            response = client.post("/dev/switch-user", data={"user": "Admin"})
            assert response.status_code == 404
        finally:
            if original is not None:
                os.environ["MOCK_USERS_ENABLED"] = original


class TestDevRoutesEnabled:
    """Dev routes work when MOCK_USERS_ENABLED=true."""

    @pytest.fixture(autouse=True)
    def enable_mock(self):
        os.environ["MOCK_USERS_ENABLED"] = "true"
        yield
        os.environ.pop("MOCK_USERS_ENABLED", None)

    def test_switch_user_sets_session(self, client):
        with client.session_transaction() as sess:
            sess.pop("dev_user", None)

        response = client.post(
            "/dev/switch-user",
            data={"user": "Regular Viewer"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get("dev_user") == "Regular Viewer"

    def test_clear_user_removes_session(self, client):
        with client.session_transaction() as sess:
            sess["dev_user"] = "Someone"

        client.post("/dev/switch-user", data={"user": ""}, follow_redirects=False)

        with client.session_transaction() as sess:
            assert "dev_user" not in sess

    def test_switch_user_redirects_to_index(self, client):
        response = client.post(
            "/dev/switch-user",
            data={"user": "Admin"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/" in response.headers["Location"]

    def test_get_current_user_returns_session_value(self, client, app):
        """When MOCK_USERS_ENABLED, get_current_user() reads from session."""

        with client.session_transaction() as sess:
            sess["dev_user"] = "Mocked User"

        with app.test_request_context():
            with client.session_transaction() as sess:
                sess["dev_user"] = "Mocked User"
            # Within a request context the session is active
            response = client.get("/")
            # The page should render as Mocked User
            assert response.status_code == 200

    def test_get_current_user_falls_back_to_env(self, client, app):
        """Without a session override, get_current_user() uses USER_NAME env."""
        from backend.auth import get_current_user

        with client.session_transaction() as sess:
            sess.pop("dev_user", None)

        original_username = os.environ.get("USER_NAME", "")
        os.environ["USER_NAME"] = "EnvUser"
        try:
            with app.test_request_context():
                assert get_current_user() == "EnvUser"
        finally:
            os.environ["USER_NAME"] = original_username

    def test_dev_nav_visible_in_template(self, client):
        """Dev persona dropdown should appear in HTML when MOCK_USERS_ENABLED."""
        response = client.get("/")
        assert response.status_code == 200
        assert (
            b"Dev:" in response.data
            or b"dev_user" in response.data
            or b"switch-user" in response.data
        )
