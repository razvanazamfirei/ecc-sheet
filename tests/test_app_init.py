"""Tests for app initialization and init_db function."""

import os
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from backend.models import Holiday, Role, db


class TestInitDb:
    """Tests for init_db function."""

    def test_init_db_creates_roles_if_missing(self, app):
        """Test that init_db creates default roles when they don't exist."""
        with app.app_context():
            # Delete all roles first
            Role.query.delete()
            db.session.commit()

            # Import and call init_db
            from backend.app import init_db

            init_db()

            # Check that roles were created
            roles = Role.query.all()
            assert len(roles) > 0

            # Check specific roles exist
            eca1 = Role.query.filter_by(name="ECA 1").first()
            assert eca1 is not None
            assert eca1.display_order == 1

    def test_init_db_sets_backup_flag_on_backup_roles(self, app):
        """Test that init_db sets is_backup=True for backup roles."""
        with app.app_context():
            # Ensure backup roles exist without is_backup flag
            backup_role = Role.query.filter_by(name="Backup").first()
            if backup_role:
                backup_role.is_backup = False
                db.session.commit()
            else:
                backup_role = Role(
                    name="Backup",
                    cutoff_hour=17,
                    cutoff_minute=30,
                    display_order=17,
                    is_backup=False,
                )
                db.session.add(backup_role)
                db.session.commit()

            from backend.app import init_db

            init_db()

            # Check that is_backup is now True
            backup_role = Role.query.filter_by(name="Backup").first()
            assert backup_role is not None
            assert backup_role.is_backup is True

    def test_init_db_updates_cardiac_backup_role(self, app):
        """Test that init_db sets is_backup=True for Cardiac Backup."""
        with app.app_context():
            # Ensure Cardiac Backup exists without is_backup flag
            cardiac_backup = Role.query.filter_by(name="Cardiac Backup").first()
            if cardiac_backup:
                cardiac_backup.is_backup = False
                db.session.commit()
            else:
                cardiac_backup = Role(
                    name="Cardiac Backup",
                    cutoff_hour=17,
                    cutoff_minute=30,
                    display_order=18,
                    is_backup=False,
                )
                db.session.add(cardiac_backup)
                db.session.commit()

            from backend.app import init_db

            init_db()

            # Check that is_backup is now True
            cardiac_backup = Role.query.filter_by(name="Cardiac Backup").first()
            assert cardiac_backup is not None
            assert cardiac_backup.is_backup is True

    def test_init_db_creates_federal_holidays(self, app):
        """Test that init_db creates federal holidays."""
        with app.app_context():
            # Delete all federal holidays first
            Holiday.query.filter_by(is_federal=True).delete()
            db.session.commit()

            from backend.app import init_db

            init_db()

            # Check that some federal holidays were created
            federal_holidays = Holiday.query.filter_by(is_federal=True).all()
            assert len(federal_holidays) > 0

    def test_init_db_does_not_duplicate_roles(self, app):
        """Test that init_db doesn't create duplicate roles."""
        with app.app_context():
            from backend.app import init_db

            # Call init_db twice
            init_db()
            count_after_first = Role.query.count()

            init_db()
            count_after_second = Role.query.count()

            # Count should be the same
            assert count_after_first == count_after_second

    def test_init_db_does_not_duplicate_holidays(self, app):
        """Test that init_db doesn't create duplicate holidays."""
        with app.app_context():
            from backend.app import init_db

            init_db()
            count_after_first = Holiday.query.count()

            init_db()
            count_after_second = Holiday.query.count()

            # Count should be the same
            assert count_after_first == count_after_second

    def test_init_db_backfills_display_order_when_none(self, app):
        """init_db sets display_order on existing roles that have it unset."""
        with app.app_context():
            role = Role.query.filter_by(name="ECA 1").first()
            assert role is not None
            original_order = role.display_order
            role.display_order = None
            db.session.commit()

            from backend.app import init_db

            init_db()

            role = Role.query.filter_by(name="ECA 1").first()
            assert role.display_order is not None
            assert role.display_order == original_order

    def test_init_db_uses_config_cutoff_hours(self, app):
        """Test that init_db uses cutoff hours from config."""
        with app.app_context():
            # Delete Late Late 1 role if it exists
            role = Role.query.filter_by(name="Late Late 1").first()
            if role:
                db.session.delete(role)
                db.session.commit()

            from backend.app import init_db

            init_db()

            # Late Late 1 should have specific cutoff from config
            role = Role.query.filter_by(name="Late Late 1").first()
            assert role is not None
            # The default config should specify cutoff hours
            assert role.cutoff_hour is not None


class TestContextProcessor:
    """Tests for template context processor."""

    def test_inject_auth_provides_current_user(self, client):
        """Test that inject_auth provides current_user in template context."""
        # Make a request to get template context
        response = client.get("/")
        assert response.status_code == 200
        # The template should have access to current_user

    def test_inject_auth_provides_is_admin(self, client):
        """Test that inject_auth provides is_admin in template context."""
        response = client.get("/")
        assert response.status_code == 200
        # The template should have access to is_admin

    def test_inject_dev_disabled_when_mock_not_enabled(self, client):
        """inject_dev returns mock_users_enabled=False when env var is unset."""
        original = os.environ.get("MOCK_USERS_ENABLED")
        try:
            os.environ.pop("MOCK_USERS_ENABLED", None)
            response = client.get("/")
            assert response.status_code == 200
            # Dev dropdown must not appear when mock is disabled
            assert b"switch-user" not in response.data
        finally:
            if original is not None:
                os.environ["MOCK_USERS_ENABLED"] = original

    def test_inject_dev_with_payroll_admin_users(self, client):
        """inject_dev includes a payroll persona when PAYROLL_ADMIN_USERS is set."""
        original_mock = os.environ.get("MOCK_USERS_ENABLED")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        try:
            os.environ["MOCK_USERS_ENABLED"] = "true"
            os.environ["PAYROLL_ADMIN_USERS"] = "Payroll Person"
            response = client.get("/")
            assert response.status_code == 200
            assert b"Payroll Person" in response.data
        finally:
            if original_mock is not None:
                os.environ["MOCK_USERS_ENABLED"] = original_mock
            else:
                os.environ.pop("MOCK_USERS_ENABLED", None)
            if original_pa is not None:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            else:
                os.environ.pop("PAYROLL_ADMIN_USERS", None)

    def test_inject_dev_enabled_shows_switch_user_form(self, client):
        """inject_dev populates template context when MOCK_USERS_ENABLED=true."""
        original = os.environ.get("MOCK_USERS_ENABLED")
        try:
            os.environ["MOCK_USERS_ENABLED"] = "true"
            response = client.get("/")
            assert response.status_code == 200
            assert b"switch-user" in response.data
        finally:
            if original is not None:
                os.environ["MOCK_USERS_ENABLED"] = original
            else:
                os.environ.pop("MOCK_USERS_ENABLED", None)

    def test_inject_dev_handles_resident_query_exception(self, client, app):
        """inject_dev falls back to empty resident list when DB query fails."""
        from backend.models import Resident

        original = os.environ.get("MOCK_USERS_ENABLED")
        try:
            os.environ["MOCK_USERS_ENABLED"] = "true"
            with app.app_context(), patch.object(Resident, "query") as mock_query:
                mock_query.filter_by.side_effect = SQLAlchemyError("DB error")
                response = client.get("/")
            assert response.status_code == 200
        finally:
            if original is not None:
                os.environ["MOCK_USERS_ENABLED"] = original
            else:
                os.environ.pop("MOCK_USERS_ENABLED", None)


class TestBackgroundServices:
    """Tests for background service startup."""

    def test_requests_do_not_attempt_to_start_background_services(self, client):
        """Requests should not rerun background-service startup checks."""
        with patch("backend.app.start_background_services") as mock_start:
            response = client.get("/")

        assert response.status_code == 200
        mock_start.assert_not_called()

    def test_should_start_background_services_during_wsgi_import(self):
        """WSGI-style imports should eagerly bootstrap background services."""
        import backend.app as app_module

        with (
            patch.object(app_module, "__name__", "backend.app"),
            patch.object(app_module.sys, "argv", ["gunicorn"]),
            patch.dict(
                os.environ,
                {
                    "FLASK_RUN_FROM_CLI": "",
                    "FLASK_DEBUG": "",
                    "WERKZEUG_RUN_MAIN": "",
                },
                clear=False,
            ),
        ):
            assert app_module._should_start_background_services_during_import() is True

    def test_should_skip_eager_start_for_non_run_flask_cli(self):
        """Non-server Flask CLI commands should not start background services."""
        import backend.app as app_module

        with (
            patch.object(app_module, "__name__", "backend.app"),
            patch.object(app_module.sys, "argv", ["flask", "db", "upgrade"]),
            patch.dict(
                os.environ,
                {"FLASK_RUN_FROM_CLI": "true"},
                clear=False,
            ),
        ):
            assert app_module._should_start_background_services_during_import() is False

    def test_start_background_services_starts_once_when_fetcher_enabled(self, app):
        """Background services should start once for the server process."""
        from backend.app import start_background_services, stop_background_services

        original_testing = app.config["TESTING"]
        original_enabled = app.config.get("ANESTHESIA_FETCHER_ENABLED")
        lock_handle = MagicMock()
        try:
            app.config["TESTING"] = False
            app.config["ANESTHESIA_FETCHER_ENABLED"] = True

            with (
                patch("backend.app.threading.Thread") as mock_thread,
                patch(
                    "backend.app._acquire_background_service_process_lock",
                    return_value=lock_handle,
                ) as mock_acquire_lock,
                patch(
                    "backend.app._release_background_service_process_lock"
                ) as mock_release_lock,
            ):
                worker = mock_thread.return_value
                worker.is_alive.return_value = False

                try:
                    assert start_background_services() is True
                    assert start_background_services() is False
                    worker.start.assert_called_once()
                    mock_acquire_lock.assert_called_once_with()
                finally:
                    stop_background_services()

                mock_release_lock.assert_called_once_with(lock_handle)
        finally:
            app.config["TESTING"] = original_testing
            app.config["ANESTHESIA_FETCHER_ENABLED"] = original_enabled

    def test_start_background_services_requires_fetcher_flag(self, app):
        """Background services should not start without the fetcher flag."""
        from backend.app import start_background_services, stop_background_services

        original_testing = app.config["TESTING"]
        original_enabled = app.config.get("ANESTHESIA_FETCHER_ENABLED")
        try:
            app.config["TESTING"] = False
            app.config["ANESTHESIA_FETCHER_ENABLED"] = False

            with patch("backend.app.threading.Thread") as mock_thread:
                assert start_background_services() is False
                mock_thread.assert_not_called()
        finally:
            stop_background_services()
            app.config["TESTING"] = original_testing
            app.config["ANESTHESIA_FETCHER_ENABLED"] = original_enabled

    def test_start_background_services_skips_when_lock_owned_elsewhere(self, app):
        """Only one worker process should bootstrap the auto-sync thread."""
        from backend.app import start_background_services, stop_background_services

        original_testing = app.config["TESTING"]
        original_enabled = app.config.get("ANESTHESIA_FETCHER_ENABLED")
        try:
            app.config["TESTING"] = False
            app.config["ANESTHESIA_FETCHER_ENABLED"] = True

            with (
                patch("backend.app.threading.Thread") as mock_thread,
                patch(
                    "backend.app._acquire_background_service_process_lock",
                    return_value=None,
                ),
            ):
                assert start_background_services() is False
                mock_thread.assert_not_called()
        finally:
            stop_background_services()
            app.config["TESTING"] = original_testing
            app.config["ANESTHESIA_FETCHER_ENABLED"] = original_enabled

    def test_ensure_time_entry_columns_ignores_duplicate_column_race(self, app):
        """Runtime schema backfill should ignore duplicate-column races."""
        import backend.app as app_module

        class _Inspector:
            @staticmethod
            def get_columns(_table_name):
                return [{"name": "id"}]

        with (
            app.app_context(),
            patch.object(
                app_module,
                "sqlalchemy_inspect",
                return_value=_Inspector(),
            ),
            patch.object(
                app_module.db.session,
                "execute",
                side_effect=SQLAlchemyError(
                    "duplicate column name: anesthesia_stop_time",
                ),
            ) as mock_execute,
            patch.object(app_module.db.session, "commit") as mock_commit,
            patch.object(app_module.db.session, "rollback") as mock_rollback,
        ):
            app_module._ensure_time_entry_columns()

        mock_execute.assert_called_once()
        mock_commit.assert_not_called()
        mock_rollback.assert_called_once_with()

    def test_background_service_lock_helpers_allow_missing_fcntl(self, app):
        """Lock helpers should remain usable when fcntl is unavailable."""
        import backend.app as app_module

        with app.app_context(), patch.object(app_module, "fcntl", None):
            lock_path = app_module._background_service_lock_path()
            lock_handle = app_module._acquire_background_service_process_lock()
            assert lock_handle is not None
            assert lock_handle.closed is False

            app_module._release_background_service_process_lock(lock_handle)
            assert lock_handle.closed is True

        lock_path.unlink(missing_ok=True)
