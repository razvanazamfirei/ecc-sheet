"""Tests for resident CSV bootstrap/import."""

import json
from datetime import date
from unittest.mock import patch

import pytest

from backend.errors import ConflictError, ValidationError
from backend.models import AuditLog, Resident, db
from backend.resident_csv_import import (
    ResidentCsvImportResult,
    import_resident_csv_records,
    import_residents_csv_file,
    parse_resident_csv,
)


class TestParseResidentCsv:
    """Tests for resident CSV parsing."""

    def test_parse_valid_csv(self):
        csv_content = (
            "name,epic_id,class_year,email,phone,abbreviation,backup_id,"
            "lawson_id,hire_date,active\n"
            "Jane Doe,R123,CA2,jane@example.com,555-0001,JD,B42,12345,"
            "2025-07-01,true\n"
        )

        records = parse_resident_csv(csv_content)

        assert len(records) == 1
        assert records[0].name == "Jane Doe"
        assert records[0].first_name == "Jane"
        assert records[0].last_name == "Doe"
        assert records[0].class_year == "CA-2"
        assert records[0].lawson_id == 12345
        assert records[0].hire_date == date(2025, 7, 1)
        assert records[0].active is True

    def test_parse_rejects_unknown_column(self):
        with pytest.raises(ValidationError, match="unsupported columns"):
            parse_resident_csv("name,badge_number\nJane Doe,123\n")

    def test_parse_rejects_invalid_email(self):
        with pytest.raises(ValidationError, match="invalid email"):
            parse_resident_csv("name,email\nJane Doe,not-an-email\n")


class TestImportResidentCsv:
    """Tests for resident CSV database import."""

    def test_import_creates_resident(self, app):
        with app.app_context():
            records = parse_resident_csv(
                "name,epic_id,class_year,email,lawson_id,hire_date\n"
                "New Bootstrap Resident,RCSV001,CA1,new@example.com,4567,2024-07-01\n"
            )

            result = import_resident_csv_records(records, user="test-user")

            resident = Resident.get_by_epic_id("RCSV001")
            assert resident is not None
            assert result == ResidentCsvImportResult(
                total_records=1,
                created=1,
                updated=0,
                skipped=0,
                dry_run=False,
            )
            assert resident.class_year == "CA-1"
            assert resident.lawson_id == 4567
            assert resident.hire_date == date(2024, 7, 1)

            db.session.delete(resident)
            db.session.commit()

    def test_import_updates_existing_resident_by_name_when_epic_missing(self, app):
        with app.app_context():
            resident = Resident(
                name="CSV Update Resident",
                first_name="CSV",
                last_name="Resident",
                class_year="CA-1",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            records = parse_resident_csv(
                "name,epic_id,class_year,email,active\n"
                "CSV Update Resident,RCSV002,CA3,updated@example.com,false\n"
            )

            result = import_resident_csv_records(records, user="test-user")

            refreshed = Resident.get_by_epic_id("RCSV002")
            assert refreshed is not None
            assert refreshed.id == resident.id
            assert refreshed.class_year == "CA-3"
            assert refreshed.email == "updated@example.com"
            assert refreshed.active is False
            assert result.updated == 1

            db.session.delete(refreshed)
            db.session.commit()

    def test_import_detects_name_epic_conflict(self, app):
        with app.app_context():
            first = Resident(name="Conflict Name", epic_id="CONFLICT_A", active=True)
            second = Resident(name="Other Name", epic_id="CONFLICT_B", active=True)
            db.session.add_all([first, second])
            db.session.commit()

            records = parse_resident_csv("name,epic_id\nConflict Name,CONFLICT_B\n")

            with pytest.raises(ConflictError, match="belongs to"):
                import_resident_csv_records(records, user="test-user")

            db.session.delete(first)
            db.session.delete(second)
            db.session.commit()

    def test_import_file_dry_run_does_not_commit(self, app, tmp_path):
        csv_path = tmp_path / "residents.csv"
        csv_path.write_text(
            "name,epic_id,class_year\nDry Run Resident,RCSVDRY,CA2\n",
            encoding="utf-8",
        )

        with app.app_context():
            result = import_residents_csv_file(csv_path, user="test-user", dry_run=True)

            assert result.dry_run is True
            assert Resident.get_by_epic_id("RCSVDRY") is None

    def test_import_persists_audit_logs_after_session_remove(self, app):
        with app.app_context():
            records = parse_resident_csv(
                "name,epic_id,class_year\nAudit Bootstrap Resident,RCSVAUDIT,CA1\n"
            )

            result = import_resident_csv_records(
                records,
                user="resident-csv-audit-test",
            )

            resident = Resident.get_by_epic_id("RCSVAUDIT")
            assert resident is not None
            assert result.created == 1
            resident_id = resident.id

            db.session.remove()

            create_log = AuditLog.query.filter_by(
                action="CREATE",
                entity_type="Resident",
                entity_id=resident_id,
            ).first()
            import_log = AuditLog.query.filter_by(
                action="IMPORT",
                entity_type="resident_csv",
                user="resident-csv-audit-test",
            ).first()
            assert create_log is not None
            assert import_log is not None

            resident = Resident.get_by_epic_id("RCSVAUDIT")
            assert resident is not None
            db.session.delete(create_log)
            db.session.delete(import_log)
            db.session.delete(resident)
            db.session.commit()

    def test_import_uses_single_flush_and_commit_for_data_and_audit(self, app):
        with app.app_context():
            records = parse_resident_csv(
                "name,epic_id,class_year\nSingle Commit Resident,RCSVONE,CA2\n"
            )

            with (
                patch.object(db.session, "flush", wraps=db.session.flush) as mock_flush,
                patch.object(
                    db.session,
                    "commit",
                    wraps=db.session.commit,
                ) as mock_commit,
            ):
                result = import_resident_csv_records(records, user="single-commit-test")

            assert result.created == 1
            mock_flush.assert_called_once_with()
            mock_commit.assert_called_once_with()

            resident = Resident.get_by_epic_id("RCSVONE")
            assert resident is not None
            create_log = AuditLog.query.filter_by(
                action="CREATE",
                entity_type="Resident",
                entity_id=resident.id,
            ).first()
            import_log = AuditLog.query.filter_by(
                action="IMPORT",
                entity_type="resident_csv",
                user="single-commit-test",
            ).first()
            assert create_log is not None
            assert import_log is not None

            db.session.delete(create_log)
            db.session.delete(import_log)
            db.session.delete(resident)
            db.session.commit()

    def test_import_update_persists_update_audit_log(self, app):
        with app.app_context():
            resident = Resident(
                name="Update Audit Resident",
                epic_id="RCSVUPD",
                class_year="CA-1",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            records = parse_resident_csv(
                "name,epic_id,class_year,email,lawson_id,hire_date\n"
                "Update Audit Resident,RCSVUPD,CA3,updated-audit@example.com,"
                "54321,2024-07-01\n"
            )

            result = import_resident_csv_records(records, user="update-audit-test")

            assert result.updated == 1
            resident_id = resident.id
            db.session.remove()

            update_log = AuditLog.query.filter_by(
                action="UPDATE",
                entity_type="Resident",
                entity_id=resident_id,
            ).first()
            import_log = AuditLog.query.filter_by(
                action="IMPORT",
                entity_type="resident_csv",
                user="update-audit-test",
            ).first()
            assert update_log is not None
            parsed = json.loads(update_log.details or "{}")
            assert parsed["changes"]["lawson_id"]["new"] == 54321
            assert parsed["changes"]["hire_date"]["new"] == "2024-07-01"
            assert "class_year" not in parsed["changes"]
            assert "email" not in parsed["changes"]
            assert import_log is not None

            refreshed = Resident.get_by_epic_id("RCSVUPD")
            assert refreshed is not None
            db.session.delete(update_log)
            db.session.delete(import_log)
            db.session.delete(refreshed)
            db.session.commit()


class TestResidentCsvCli:
    """Tests for resident CSV CLI commands."""

    def test_cli_import_bootstraps_schema_before_import(
        self, runner, monkeypatch, tmp_path
    ):
        csv_path = tmp_path / "residents.csv"
        csv_path.write_text("name\nCLI Resident\n", encoding="utf-8")
        call_order: list[str] = []

        def _fake_ensure_runtime_schema():
            call_order.append("ensure_runtime_schema")

        def _fake_import(csv_arg, *, user, dry_run):
            call_order.append("import")
            assert csv_arg == csv_path
            assert user == "Admin"
            assert dry_run is False
            return ResidentCsvImportResult(
                total_records=1,
                created=1,
                updated=0,
                skipped=0,
                dry_run=False,
            )

        monkeypatch.setattr(
            "backend.app._ensure_runtime_schema", _fake_ensure_runtime_schema
        )
        monkeypatch.setattr("backend.app.import_residents_csv_file", _fake_import)

        result = runner.invoke(
            args=["import-residents-csv", "--path", str(csv_path)],
        )

        assert result.exit_code == 0
        assert call_order == ["ensure_runtime_schema", "import"]

    def test_cli_imports_residents_from_csv(self, runner, app, tmp_path):
        csv_path = tmp_path / "residents.csv"
        csv_path.write_text(
            "name,epic_id,class_year,email\nCLI Resident,RCSVCLI,CA2,cli@example.com\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            args=["import-residents-csv", "--path", str(csv_path)],
        )

        assert result.exit_code == 0
        assert "processed 1 resident records" in result.output.casefold()

        with app.app_context():
            resident = Resident.get_by_epic_id("RCSVCLI")
            assert resident is not None
            db.session.delete(resident)
            db.session.commit()

    def test_bootstrap_command_runs_init_and_optional_import(
        self, runner, monkeypatch, tmp_path
    ):
        csv_path = tmp_path / "bootstrap.csv"
        csv_path.write_text("name\nBootstrap Resident\n", encoding="utf-8")
        calls: dict[str, object] = {}

        def _fake_init_db():
            calls["init_db"] = True

        def _fake_import(csv_arg, *, user, dry_run):
            calls["csv_arg"] = csv_arg
            calls["user"] = user
            calls["dry_run"] = dry_run
            return ResidentCsvImportResult(
                total_records=1,
                created=1,
                updated=0,
                skipped=0,
                dry_run=False,
            )

        monkeypatch.setattr("backend.app.init_db", _fake_init_db)
        monkeypatch.setattr("backend.app.import_residents_csv_file", _fake_import)

        result = runner.invoke(
            args=["bootstrap-application", "--residents-csv", str(csv_path)],
        )

        assert result.exit_code == 0
        assert calls["init_db"] is True
        assert calls["csv_arg"] == csv_path
        assert calls["user"] == "Admin"
        assert calls["dry_run"] is False
        assert "schema and default data bootstrapped" in result.output.casefold()
