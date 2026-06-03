"""Tests for first-party SAML SSO routes and guards."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.security.saml import saml_logout_enabled


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
        self.logout_calls: list[dict[str, object]] = []
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

    def logout(self, **kwargs: object) -> str:
        self.logout_calls.append(kwargs)
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
    def test_login_redirects_when_idp_slo_url_is_invalid(
        self,
        client,
        app,
        monkeypatch,
    ):
        fake_auth = _FakeSamlAuth(logout_url="")
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
        with patch("backend.routes.sso.build_saml_auth", return_value=fake_auth):
            response = client.get("/auth/login?next=/reports")

        assert response.status_code == 302
        assert response.headers["Location"] == "https://idp.example.test/sso"
        with client.session_transaction() as sess:
            assert sess["saml_request_id"]

    def test_login_redirects_to_idp_and_stores_request_id(
        self,
        client,
        app,
        monkeypatch,
    ):
        fake_auth = _FakeSamlAuth()
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
        with patch("backend.routes.sso.build_saml_auth", return_value=fake_auth):
            response = client.get("/auth/login?next=/reports")

        assert response.status_code == 302
        assert response.headers["Location"] == "https://idp.example.test/sso"
        assert fake_auth.login_calls == ["/reports"]
        with client.session_transaction() as sess:
            assert sess["saml_request_id"] == "req-123"

    def test_acs_sets_session_user_and_redirects(self, client, app, monkeypatch):
        fake_auth = _FakeSamlAuth(request_id="req-456")
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
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

    def test_acs_prefers_identity_attribute_for_session_user(
        self,
        client,
        app,
        monkeypatch,
    ):
        fake_auth = _FakeSamlAuth(
            request_id="req-456",
            attributes={"Identity": ["AzamfirR"], "name": ["SAML User"]},
        )
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
        with client.session_transaction() as sess:
            sess["saml_request_id"] = "req-123"

        with patch("backend.routes.sso.build_saml_auth", return_value=fake_auth):
            response = client.post("/auth/acs", data={"RelayState": "/reports"})

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/reports")
        with client.session_transaction() as sess:
            assert sess["auth_user"] == "AzamfirR"

    def test_metadata_returns_xml(self, client, app, monkeypatch):
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
        with patch(
            "backend.routes.sso.build_saml_settings",
            return_value=_FakeSamlSettings(),
        ):
            response = client.get("/auth/metadata")

        assert response.status_code == 200
        assert response.mimetype == "application/samlmetadata+xml"
        assert response.data == b"<xml>metadata</xml>"

    def test_logout_clears_local_session_when_build_saml_auth_raises(
        self,
        client,
        app,
        monkeypatch,
    ):
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
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

    def test_logout_sends_saml_request_to_auth0_samlp_logout_endpoint(
        self,
        client,
        app,
        monkeypatch,
    ):
        fake_auth = _FakeSamlAuth(
            request_id="slo-req-1",
            logout_url="https://example.auth0.com/samlp/client_123/logout",
        )
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
        with client.session_transaction() as sess:
            sess["auth_user"] = "SAML User"
            sess["saml_authn"] = {
                "name_id": "nameid@example.test",
                "session_index": "session-123",
            }

        with (
            patch("backend.routes.sso.saml_logout_enabled", return_value=True),
            patch("backend.routes.sso.build_saml_auth", return_value=fake_auth),
        ):
            response = client.get("/auth/logout?next=/reports")

        assert response.status_code == 302
        assert response.headers["Location"].startswith(
            "https://example.auth0.com/samlp/client_123/logout"
        )
        with client.session_transaction() as sess:
            assert "auth_user" not in sess
            assert "saml_authn" not in sess
            assert sess["saml_logout_request_id"]

    def test_logout_does_not_derive_from_non_samlp_sso_url(
        self,
        client,
        app,
        monkeypatch,
    ):
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
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

    def test_logout_uses_saml_slo_and_clears_local_session_before_redirect(
        self,
        client,
        app,
        monkeypatch,
    ):
        fake_auth = _FakeSamlAuth(request_id="logout-123")
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
        with client.session_transaction() as sess:
            sess["auth_user"] = "SAML User"
            sess["saml_authn"] = {
                "name_id": "nameid@example.test",
                "session_index": "session-123",
            }

        with (
            patch("backend.routes.sso.saml_logout_enabled", return_value=True),
            patch("backend.routes.sso.build_saml_auth", return_value=fake_auth),
        ):
            response = client.get("/auth/logout?next=/reports")

        assert response.status_code == 302
        assert response.headers["Location"] == "https://idp.example.test/logout"
        assert fake_auth.logout_calls == [
            {
                "return_to": "/reports",
                "name_id": "nameid@example.test",
                "session_index": "session-123",
            }
        ]
        with client.session_transaction() as sess:
            assert "auth_user" not in sess
            assert "saml_authn" not in sess
            assert sess["saml_logout_request_id"] == "logout-123"

    def test_logout_clears_local_session_when_slo_not_configured(
        self,
        client,
        app,
        monkeypatch,
    ):
        monkeypatch.setitem(app.config, "SAML_ENABLED", True)
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


class TestSamlLogoutSettings:
    def test_saml_logout_enabled_derives_from_auth0_samlp_sso_url(self):
        fake_settings = {
            "idp": {
                "singleSignOnService": {
                    "url": "https://example.auth0.com/samlp/client_123"
                },
                "singleLogoutService": {
                    "url": "https://example.auth0.com/samlp/client_123/logout"
                },
            },
        }
        with patch(
            "backend.security.saml.load_saml_settings",
            return_value=(fake_settings, None),
        ):
            assert saml_logout_enabled({}) is True

    @pytest.mark.parametrize(
        "slo_settings",
        [
            {},
            {"url": ""},
        ],
    )
    def test_saml_logout_disabled_when_idp_slo_url_is_invalid_or_blank(
        self,
        slo_settings,
    ):
        fake_settings = {"idp": {"singleLogoutService": slo_settings}}
        with patch(
            "backend.security.saml.load_saml_settings",
            return_value=(fake_settings, None),
        ):
            assert saml_logout_enabled({}) is False

    def test_saml_logout_enabled_when_idp_slo_url_is_valid(self):
        fake_settings = {
            "idp": {
                "singleLogoutService": {"url": "https://idp.example.test/logout"},
            },
        }
        with patch(
            "backend.security.saml.load_saml_settings",
            return_value=(fake_settings, None),
        ):
            assert saml_logout_enabled({}) is True
