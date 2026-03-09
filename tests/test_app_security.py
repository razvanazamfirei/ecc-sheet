"""Security tests for app-level request handling."""

from flask import url_for
from flask_wtf.csrf import CSRFError

from backend.app import handle_csrf_error


class TestCsrfErrorHandling:
    """Tests for CSRF failure responses."""

    def test_csrf_redirect_allows_same_origin_referrer(self, app):
        """Normal same-origin referrers remain valid redirect targets."""
        with app.test_request_context(
            "/reports",
            headers={"Referer": "http://localhost/reports"},
            base_url="http://localhost",
        ):
            response = handle_csrf_error(CSRFError("expired"))

        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/reports"

    def test_csrf_redirect_rejects_external_referrer(self, app):
        """External referrers fall back to the safe sheets index route."""
        with app.test_request_context(
            "/reports",
            headers={"Referer": "https://evil.example/phish"},
            base_url="http://localhost",
        ):
            response = handle_csrf_error(CSRFError("expired"))
            expected_location = url_for("sheets.index")

        assert response.status_code == 302
        assert response.headers["Location"] == expected_location
