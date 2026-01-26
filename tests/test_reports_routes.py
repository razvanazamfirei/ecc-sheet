"""Tests for report routes."""

from backend.models import TimeEntry


class TestReportGeneration:
    """Tests for report generation."""

    def test_reports_page_loads(self, client):
        """Test that reports page loads."""
        response = client.get("/reports")
        assert response.status_code == 200

    def test_generate_report_with_entries(self, client, app, sample_time_entry):
        """Test generating a report with entries."""
        with app.app_context():
            entry = TimeEntry.query.get(sample_time_entry.id)
            entry_date = entry.date

            response = client.post(
                "/api/report",
                data={
                    "start_date": entry_date.strftime("%Y-%m-%d"),
                    "end_date": entry_date.strftime("%Y-%m-%d"),
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Overtime" in response.data

    def test_generate_report_filtered_by_resident(
        self, client, app, sample_time_entry, sample_resident
    ):
        """Test generating a report filtered by resident."""
        with app.app_context():
            entry = TimeEntry.query.get(sample_time_entry.id)
            entry_date = entry.date

            response = client.post(
                "/api/report",
                data={
                    "start_date": entry_date.strftime("%Y-%m-%d"),
                    "end_date": entry_date.strftime("%Y-%m-%d"),
                    "resident_id": sample_resident.id,
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_generate_report_invalid_date(self, client):
        """Test generating a report with invalid date."""
        response = client.post(
            "/api/report",
            data={
                "start_date": "invalid",
                "end_date": "2024-01-31",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should redirect with error flash


class TestReportExport:
    """Tests for report CSV export."""

    def test_export_csv_empty(self, client):
        """Test exporting empty report as CSV."""
        response = client.post(
            "/api/report/export_csv",
            data={
                "start_date": "2020-01-01",
                "end_date": "2020-01-31",
            },
        )
        assert response.status_code == 200
        assert "text/csv" in response.content_type
        assert b"Date,Resident,Role" in response.data

    def test_export_csv_with_entries(self, client, app, sample_time_entry):
        """Test exporting report with entries as CSV."""
        with app.app_context():
            entry = TimeEntry.query.get(sample_time_entry.id)
            entry_date = entry.date

            response = client.post(
                "/api/report/export_csv",
                data={
                    "start_date": entry_date.strftime("%Y-%m-%d"),
                    "end_date": entry_date.strftime("%Y-%m-%d"),
                },
            )
            assert response.status_code == 200
            assert "text/csv" in response.content_type
            # Check filename in Content-Disposition
            assert "overtime_report" in response.headers.get("Content-Disposition", "")

    def test_export_csv_filtered_by_resident(
        self, client, app, sample_time_entry, sample_resident
    ):
        """Test exporting filtered report as CSV."""
        with app.app_context():
            entry = TimeEntry.query.get(sample_time_entry.id)
            entry_date = entry.date

            response = client.post(
                "/api/report/export_csv",
                data={
                    "start_date": entry_date.strftime("%Y-%m-%d"),
                    "end_date": entry_date.strftime("%Y-%m-%d"),
                    "resident_id": sample_resident.id,
                },
            )
            assert response.status_code == 200
            assert "text/csv" in response.content_type
