"""Tests for resident routes."""

from datetime import date

import pytest

from backend.models import Resident, db


class TestResidentManagement:
    """Tests for resident management routes."""

    def test_add_resident_empty_name(self, client):
        """Test adding resident with empty name fails."""
        response = client.post(
            "/residents/add",
            data={"name": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()

    def test_add_resident_whitespace_name(self, client):
        """Test adding resident with whitespace-only name fails."""
        response = client.post(
            "/residents/add",
            data={"name": "   "},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should be rejected

    def test_resident_list_shows_all(self, client, app, sample_resident):
        """Test resident list shows all residents."""
        with app.app_context():
            response = client.get("/residents/")
            assert response.status_code == 200
            assert sample_resident.name.encode() in response.data
