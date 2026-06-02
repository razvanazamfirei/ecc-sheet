"""Tests for first-party SAML SSO routes and guards."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class _FakeSamlAuth:
    def __init__(self, **overrides: object) -> None:
        self._login_url = str(
            overrides.get("login_url", "https://idp.example.test/sso")
        )
        self._request_id = str(overrides.get("request_id", "req-123"))
        self._errors = list(overrides.get("errors", []))
        self._authenticated = bool(overrides.get("authenticated", True))
        self._attributes = dict(overrides.get("attributes", {"name": ["SAML User"]}))
        self._name_id = str(overrides.get("name_id", "nameid@example.test"))
        self._session_index = str(overrides.get("session_index", "session-123"))
        self._logout_url = str(
            overrides.get("logout_url", "https://idp.example.test/logout")
        )
        self._sls_redirect_url = overrides.get("sls_redirect_url")
        self.login_calls: list[str | None] = []
        self.process_response_request_ids: list[str | None] = []
        self.process_slo_request_ids: list[str | None] = []

    def login(self, *, return_to: str | None = None, **_: object) -> str:
        self.login_calls.append(return_to)
        return self._login_url

    def get_last_request_id(self) -> str:
        return self._request_id

    def process_response(self, *, request_id: str | None = None) -> None:
        self.process_response_request_ids.append(request_id)

    def get_errors(self) -> list[str]:
        return self._errors

    def get_last_error_reason(self) -> str:
        return "bad-response"

    def is_authenticated(self) -> bool:
        return self._authenticated

    def get_attributes(self) -> dict[str, list[str]]:
        return self._attributes

    def get_nameid(self) -> str:
        return self._name_id

    def get_session_index(self) -> str:
        return self._session_index

    def logout(self, **_: object) -> str:
        return self._logout_url

    def process_slo(
        self,
        *,
        request_id: str | None = None,
        delete_session_cb=None,
        **_: object,
    ) -> str | None:
        self.process_slo_request_ids.append(request_id)
        if delete_session_cb is not None:
            delete_session_cb()
        return self._sls_redirect_url


class _FakeSamlSettings:
    def get_sp_metadata(self) -> str:
        return "<xml>metadata</xml>"

    def validate_metadata(self, _metadata: str) -> list[str]:
        return []


@pytest.mark.usefixtures("saml_enabled_app")
class TestSamlGuard:
    def test_saml_redirects_unauthenticated_browser_requests_to_login(
        self,
        client,
    ):
        response = client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"] == "/auth/login?next=/"

    def test_saml_returns_401_for_json_requests(
        self,
        client,
    ):
        response = client.get(
            "/api/residents/active",
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 401
        assert response.get_json() == {
            "success": False,
            "message": "Authentication required.",
        }


class TestSamlRoutes:
    def test_login_redirects_to_idp_and_stores_request_id(self, client, app):
        original = app.config["SAML_ENABLED"]
        fake_auth = _FakeSamlAuth()
        try:
            app.config["SAML_ENABLED"] = True
            with patch("backend.routes.sso.build_saml_auth", return_value=fake_auth):
                response = client.get("/auth/login?next=/reports")

            assert response.status_code == 302
            assert response.headers["Location"] == "https://idp.example.test/sso"
            assert fake_auth.login_calls == ["/reports"]
            with client.session_transaction() as sess:
                assert sess["saml_request_id"] == "req-123"
        finally:
            app.config["SAML_ENABLED"] = original

    def test_acs_sets_session_user_and_redirects(self, client, app):
        original = app.config["SAML_ENABLED"]
        fake_auth = _FakeSamlAuth(request_id="req-456")
        try:
            app.config["SAML_ENABLED"] = True
            with client.session_transaction() as sess:
                sess["saml_request_id"] = "req-123"

            with patch("backend.routes.sso.build_saml_auth", return_value=fake_auth):
                response = client.post("/auth/acs", data={"RelayState": "/reports"})

            assert response.status_code == 302
            assert response.headers["Location"].endswith("/reports")
            assert fake_auth.process_response_request_ids == ["req-123"]
            with client.session_transaction() as sess:
                assert sess["auth_user"] == "SAML User"
                assert sess["saml_authn"]["name_id"] == "nameid@example.test"
                assert sess["saml_authn"]["session_index"] == "session-123"
        finally:
            app.config["SAML_ENABLED"] = original

    def test_acs_prefers_identity_attribute_for_session_user(self, client, app):
        original = app.config["SAML_ENABLED"]
        fake_auth = _FakeSamlAuth(
            request_id="req-456",
            attributes={"Identity": ["AzamfirR"], "name": ["SAML User"]},
        )
        try:
            app.config["SAML_ENABLED"] = True
            with client.session_transaction() as sess:
                sess["saml_request_id"] = "req-123"

            with patch("backend.routes.sso.build_saml_auth", return_value=fake_auth):
                response = client.post("/auth/acs", data={"RelayState": "/reports"})

            assert response.status_code == 302
            assert response.headers["Location"].endswith("/reports")
            with client.session_transaction() as sess:
                assert sess["auth_user"] == "AzamfirR"
        finally:
            app.config["SAML_ENABLED"] = original

    def test_metadata_returns_xml(self, client, app):
        original = app.config["SAML_ENABLED"]
        try:
            app.config["SAML_ENABLED"] = True
            with patch(
                "backend.routes.sso.build_saml_settings",
                return_value=_FakeSamlSettings(),
            ):
                response = client.get("/auth/metadata")

            assert response.status_code == 200
            assert response.mimetype == "application/samlmetadata+xml"
            assert response.data == b"<xml>metadata</xml>"
        finally:
            app.config["SAML_ENABLED"] = original

    def test_logout_clears_local_session_when_build_saml_auth_raises(self, client, app):
        original = app.config["SAML_ENABLED"]
        try:
            app.config["SAML_ENABLED"] = True
            with client.session_transaction() as sess:
                sess["auth_user"] = "SAML User"

            with (
                patch("backend.routes.sso.saml_logout_enabled", return_value=True),
                patch(
                    "backend.routes.sso.build_saml_auth",
                    side_effect=Exception("idp_slo_url_invalid"),
                ),
            ):
                response = client.get("/auth/logout")

            assert response.status_code == 302
            with client.session_transaction() as sess:
                assert "auth_user" not in sess
        finally:
            app.config["SAML_ENABLED"] = original

    def test_logout_clears_local_session_when_slo_not_configured(self, client, app):
        original = app.config["SAML_ENABLED"]
        try:
            app.config["SAML_ENABLED"] = True
            with client.session_transaction() as sess:
                sess["auth_user"] = "SAML User"
                sess["saml_authn"] = {"name_id": "nameid@example.test"}

            with patch("backend.routes.sso.saml_logout_enabled", return_value=False):
                response = client.get("/auth/logout?next=/reports")

            assert response.status_code == 302
            assert response.headers["Location"].endswith("/reports")
            with client.session_transaction() as sess:
                assert "auth_user" not in sess
                assert "saml_authn" not in sess
        finally:
            app.config["SAML_ENABLED"] = original
