"""Tests for report routes."""

from backend.models import TimeEntry, db


class TestReportGeneration:
    """Tests for report generation."""

    def test_reports_page_loads(self, client):
        """Test that reports page loads."""
        response = client.get("/reports")
        assert response.status_code == 200

    def test_generate_report_with_entries(self, client, app, sample_time_entry):
        """Test generating a report with entries."""
        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
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
            entry = db.session.get(TimeEntry, sample_time_entry.id)
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
            entry = db.session.get(TimeEntry, sample_time_entry.id)
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
            entry = db.session.get(TimeEntry, sample_time_entry.id)
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

    def test_export_csv_invalid_date(self, client):
        """Test exporting CSV with invalid date redirects."""
        response = client.post(
            "/api/report/export_csv",
            data={
                "start_date": "invalid",
                "end_date": "2024-01-31",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should show error message
        assert b"invalid" in response.data.lower() or b"error" in response.data.lower()


class TestReportEmail:
    """Tests for emailing reports."""

    def test_send_email_success(self, client, app, sample_time_entry):
        """Test sending report email successfully."""
        from unittest.mock import patch

        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            entry_date = entry.date

            with patch("backend.routes.reports.send_report_email", return_value=True):
                response = client.post(
                    "/api/report/send_email",
                    data={
                        "start_date": entry_date.strftime("%Y-%m-%d"),
                        "end_date": entry_date.strftime("%Y-%m-%d"),
                        "recipient_email": "test@example.com",
                    },
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"emailed successfully" in response.data

    def test_send_email_failure(self, client, app, sample_time_entry):
        """Test handling email send failure."""
        from unittest.mock import patch

        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            entry_date = entry.date

            with patch("backend.routes.reports.send_report_email", return_value=False):
                response = client.post(
                    "/api/report/send_email",
                    data={
                        "start_date": entry_date.strftime("%Y-%m-%d"),
                        "end_date": entry_date.strftime("%Y-%m-%d"),
                        "recipient_email": "test@example.com",
                    },
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"Failed to send email" in response.data

    def test_send_email_exception(self, client, app, sample_time_entry):
        """Test handling exception during email send."""
        from unittest.mock import patch

        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            entry_date = entry.date

            with patch(
                "backend.routes.reports.send_report_email",
                side_effect=Exception("SMTP error"),
            ):
                response = client.post(
                    "/api/report/send_email",
                    data={
                        "start_date": entry_date.strftime("%Y-%m-%d"),
                        "end_date": entry_date.strftime("%Y-%m-%d"),
                        "recipient_email": "test@example.com",
                    },
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"Error sending email" in response.data

    def test_send_email_with_resident_filter(self, client, app, sample_time_entry, sample_resident):
        """Test sending email with resident filter."""
        from unittest.mock import patch

        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            entry_date = entry.date

            with patch("backend.routes.reports.send_report_email", return_value=True):
                response = client.post(
                    "/api/report/send_email",
                    data={
                        "start_date": entry_date.strftime("%Y-%m-%d"),
                        "end_date": entry_date.strftime("%Y-%m-%d"),
                        "resident_id": sample_resident.id,
                        "recipient_email": "test@example.com",
                    },
                    follow_redirects=True,
                )
                assert response.status_code == 200

    def test_send_email_no_recipient(self, client, app, sample_time_entry):
        """Test sending email without explicit recipient uses config."""
        from unittest.mock import patch

        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            entry_date = entry.date

            with patch("backend.routes.reports.send_report_email", return_value=True):
                response = client.post(
                    "/api/report/send_email",
                    data={
                        "start_date": entry_date.strftime("%Y-%m-%d"),
                        "end_date": entry_date.strftime("%Y-%m-%d"),
                    },
                    follow_redirects=True,
                )
                assert response.status_code == 200


class TestReportEdgeCases:
    """Edge case tests for reports."""

    def test_generate_report_date_range(self, client, app):
        """Test report with wide date range."""
        response = client.post(
            "/api/report",
            data={
                "start_date": "2020-01-01",
                "end_date": "2025-12-31",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_generate_report_same_day(self, client, app, sample_time_entry):
        """Test report for a single day."""
        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            entry_date = entry.date
            date_str = entry_date.strftime("%Y-%m-%d")

            response = client.post(
                "/api/report",
                data={
                    "start_date": date_str,
                    "end_date": date_str,
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
