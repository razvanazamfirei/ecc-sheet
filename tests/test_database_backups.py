"""Tests for database backup helpers."""

import pathlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.database.backups import backup_database


@pytest.mark.unit
class TestBackupDatabase:
    """Test database backup functionality."""

    def test_backup_database_creates_file(self, app, tmp_path):
        """Test that backup creates a file."""
        with app.app_context():
            backup_dir = Path(tmp_path / "backups")
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            result = backup_database(db_path, backup_dir)

            assert result is True
            assert pathlib.Path(backup_dir).exists()
            backups = list(pathlib.Path(backup_dir).iterdir())
            assert len(backups) > 0
            assert backups[0].name.endswith(".db")

    def test_backup_database_nonexistent_file(self, tmp_path):
        """Test backup of non-existent database."""
        result = backup_database(Path("nonexistent.db"), tmp_path)

        assert result is False


@pytest.mark.unit
class TestBackupDatabaseEdgeCases:
    """Additional edge case tests for backup_database."""

    def test_backup_creates_directory_if_missing(self, app, tmp_path):
        """Test backup creates backup directory if it doesn't exist."""
        with app.app_context():
            backup_dir = tmp_path / "new_backup_dir"
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            result = backup_database(db_path, backup_dir)

            assert result is True
            assert backup_dir.exists()

    def test_backup_cleans_old_backups(self, app, tmp_path):
        """Test backup removes old backups beyond 30."""
        with app.app_context():
            backup_dir = tmp_path / "backups"
            backup_dir.mkdir()

            for i in range(35):
                (backup_dir / f"ecc_sheet_{i:02d}.db").touch()

            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            result = backup_database(db_path, backup_dir)

            assert result is True
            backup_files = list(backup_dir.glob("ecc_sheet_*.db"))
            assert len(backup_files) <= 31


@pytest.mark.unit
class TestBackupDatabaseExceptionHandling:
    """Test backup_database exception handling."""

    def test_backup_database_handles_backup_error(self, app, tmp_path, monkeypatch):
        """Test backup handles SQLite backup errors gracefully."""
        with app.app_context():
            backup_dir = tmp_path / "backups"
            backup_dir.mkdir()
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            mock_source = MagicMock()
            mock_source.backup = MagicMock(side_effect=OSError("Backup failed"))

            def mock_connect(*_args, **_kwargs):
                conn = MagicMock()
                conn.__enter__.return_value = mock_source
                return conn

            monkeypatch.setattr(
                "backend.database.backups.sqlite3.connect", mock_connect
            )

            result = backup_database(db_path, backup_dir)

            assert result is False

    def test_backup_database_handles_mkdir_error(self, app, tmp_path):
        """Test backup handles directory creation errors gracefully."""
        with app.app_context():
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
            backup_dir = tmp_path / "readonly_dir"

            with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
                result = backup_database(db_path, backup_dir)

        assert result is False
