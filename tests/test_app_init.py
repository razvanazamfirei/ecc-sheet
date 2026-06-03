"""Tests for app initialization and init_db function."""

from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from backend.database.bootstrap import init_db
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
            init_db(app)

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
            init_db(app)

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
            init_db(app)

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
            init_db(app)

            # Check that some federal holidays were created
            federal_holidays = Holiday.query.filter_by(is_federal=True).all()
            assert len(federal_holidays) > 0

    def test_init_db_does_not_duplicate_roles(self, app):
        """Test that init_db doesn't create duplicate roles."""
        with app.app_context():
            # Call init_db twice
            init_db(app)
            count_after_first = Role.query.count()

            init_db(app)
            count_after_second = Role.query.count()

            # Count should be the same
            assert count_after_first == count_after_second

    def test_init_db_does_not_duplicate_holidays(self, app):
        """Test that init_db doesn't create duplicate holidays."""
        with app.app_context():
            init_db(app)
            count_after_first = Holiday.query.count()

            init_db(app)
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
            init_db(app)

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
            init_db(app)

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

    def test_inject_dev_disabled_when_mock_not_enabled(self, client, app, monkeypatch):
        """inject_dev returns mock_users_enabled=False when env var is unset."""
        monkeypatch.setitem(app.config, "MOCK_USERS_ENABLED", False)
        response = client.get("/")
        assert response.status_code == 200
        assert b"switch-user" not in response.data

    def test_inject_dev_with_payroll_admin_users(self, client, app, monkeypatch):
        """inject_dev includes a payroll persona when PAYROLL_ADMIN_USERS is set."""
        monkeypatch.setitem(app.config, "MOCK_USERS_ENABLED", "true")
        monkeypatch.setitem(app.config, "PAYROLL_ADMIN_USERS", "Payroll Person")
        response = client.get("/")
        assert response.status_code == 200
        assert b"Payroll Person" in response.data

    def test_inject_dev_enabled_shows_switch_user_form(self, client, app, monkeypatch):
        """inject_dev populates template context when MOCK_USERS_ENABLED=true."""
        monkeypatch.setitem(app.config, "MOCK_USERS_ENABLED", "true")
        response = client.get("/")
        assert response.status_code == 200
        assert b"switch-user" in response.data

    def test_inject_dev_handles_resident_query_exception(
        self, client, app, monkeypatch
    ):
        """inject_dev falls back to empty resident list when DB query fails."""
        from backend.models import Resident

        monkeypatch.setitem(app.config, "MOCK_USERS_ENABLED", "true")
        with app.app_context(), patch.object(Resident, "query") as mock_query:
            mock_query.filter_by.side_effect = SQLAlchemyError("DB error")
            response = client.get("/")
        assert response.status_code == 200


class TestBackgroundServices:
    """Tests for background service startup."""

    def test_runtime_schema_hook_runs_when_not_cached(self, client, app):
        """Uncached requests should still bootstrap the runtime schema."""
        original_checked = app.extensions.pop("runtime_schema_checked", None)
        try:
            with patch("backend.app._ensure_runtime_schema") as mock_ensure:
                response = client.get("/")

            assert response.status_code == 200
            mock_ensure.assert_called_once_with()
        finally:
            if original_checked is not None:
                app.extensions["runtime_schema_checked"] = original_checked

    def test_runtime_schema_hook_skips_when_cached(self, client, app):
        """Cached requests should bypass runtime schema bootstrap."""
        original_checked = app.extensions.get("runtime_schema_checked")
        app.extensions["runtime_schema_checked"] = True
        try:
            with patch("backend.app._ensure_runtime_schema") as mock_ensure:
                response = client.get("/")

            assert response.status_code == 200
            mock_ensure.assert_not_called()
        finally:
            if original_checked is None:
                app.extensions.pop("runtime_schema_checked", None)
            else:
                app.extensions["runtime_schema_checked"] = original_checked

    def test_runtime_schema_hook_skips_static_requests(self, client):
        """Static asset requests should bypass runtime schema bootstrap."""
        with patch("backend.app._ensure_runtime_schema") as mock_ensure:
            response = client.get("/static/css/style.css")

        assert response.status_code == 200
        mock_ensure.assert_not_called()

    def test_requests_do_not_attempt_to_start_background_services(self, client):
        """Requests should not rerun background-service startup checks."""
        with patch("backend.app._start_background_services") as mock_start:
            response = client.get("/")

        assert response.status_code == 200
        mock_start.assert_not_called()

    def test_should_start_background_services_during_wsgi_import(self, monkeypatch):
        """WSGI-style imports should eagerly bootstrap background services."""
        from backend import background_services

        monkeypatch.setenv("FLASK_RUN_FROM_CLI", "")
        monkeypatch.setenv("FLASK_DEBUG", "")
        monkeypatch.setenv("WERKZEUG_RUN_MAIN", "")
        assert (
            background_services.should_start_background_services_during_import(
                module_name="backend.app",
                argv=["gunicorn"],
            )
            is True
        )

    def test_should_skip_eager_start_for_non_run_flask_cli(self, monkeypatch):
        """Non-server Flask CLI commands should not start background services."""
        from backend import background_services

        monkeypatch.setenv("FLASK_RUN_FROM_CLI", "true")
        assert (
            background_services.should_start_background_services_during_import(
                module_name="backend.app",
                argv=["flask", "db", "upgrade"],
            )
            is False
        )

    def test_auto_sync_config_helpers_clamp_values(self, app, monkeypatch):
        """Automatic sync config helpers enforce safe lower bounds."""
        from backend import background_services

        monkeypatch.setitem(app.config, "ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS", -3)
        monkeypatch.setitem(app.config, "ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS", 5)

        assert background_services._auto_sync_lookback_days(app) == 0
        assert background_services._auto_sync_interval_seconds(app) == 300

    def test_start_background_services_starts_once_when_fetcher_enabled(
        self, app, monkeypatch
    ):
        """Background services should start once for the server process."""
        from backend.background_services import (
            start_background_services,
            stop_background_services,
        )

        monkeypatch.setitem(app.config, "TESTING", False)
        monkeypatch.setitem(app.config, "ANESTHESIA_FETCHER_ENABLED", True)
        lock_handle = MagicMock()
        with (
            patch("backend.background_services.threading.Thread") as mock_thread,
            patch(
                "backend.background_services._acquire_background_service_process_lock",
                return_value=lock_handle,
            ) as mock_acquire_lock,
            patch(
                "backend.background_services._release_background_service_process_lock"
            ) as mock_release_lock,
        ):
            worker = mock_thread.return_value
            worker.is_alive.return_value = False

            try:
                assert start_background_services(app, lambda: None) is True
                assert start_background_services(app, lambda: None) is False
                worker.start.assert_called_once()
                mock_acquire_lock.assert_called_once_with(app)
            finally:
                stop_background_services(app)

            mock_release_lock.assert_called_once_with(lock_handle)

    def test_start_background_services_requires_fetcher_flag(self, app, monkeypatch):
        """Background services should not start without the fetcher flag."""
        from backend.background_services import (
            start_background_services,
            stop_background_services,
        )

        monkeypatch.setitem(app.config, "TESTING", False)
        monkeypatch.setitem(app.config, "ANESTHESIA_FETCHER_ENABLED", False)
        try:
            with patch("backend.background_services.threading.Thread") as mock_thread:
                assert start_background_services(app, lambda: None) is False
                mock_thread.assert_not_called()
        finally:
            stop_background_services(app)

    def test_start_background_services_skips_when_lock_owned_elsewhere(
        self, app, monkeypatch
    ):
        """Only one worker process should bootstrap the auto-sync thread."""
        from backend.background_services import (
            start_background_services,
            stop_background_services,
        )

        monkeypatch.setitem(app.config, "TESTING", False)
        monkeypatch.setitem(app.config, "ANESTHESIA_FETCHER_ENABLED", True)
        try:
            with (
                patch("backend.background_services.threading.Thread") as mock_thread,
                patch(
                    "backend.background_services._acquire_background_service_process_lock",
                    return_value=None,
                ),
            ):
                assert start_background_services(app, lambda: None) is False
                mock_thread.assert_not_called()
        finally:
            stop_background_services(app)

    def test_ensure_time_entry_columns_ignores_duplicate_column_race(self, app):
        """Runtime schema backfill should ignore duplicate-column races."""
        from backend.database import runtime_schema

        class _Inspector:
            @staticmethod
            def get_columns(_table_name) -> list[dict[str, str]]:
                return [{"name": "id"}]

        with (
            app.app_context(),
            patch.object(
                runtime_schema,
                "sqlalchemy_inspect",
                return_value=_Inspector(),
            ),
            patch.object(
                runtime_schema.db.session,
                "execute",
                side_effect=SQLAlchemyError(
                    "duplicate column name: anesthesia_stop_time",
                ),
            ) as mock_execute,
            patch.object(runtime_schema.db.session, "commit") as mock_commit,
            patch.object(runtime_schema.db.session, "rollback") as mock_rollback,
        ):
            runtime_schema.ensure_time_entry_columns()

        mock_execute.assert_called_once()
        mock_commit.assert_not_called()
        mock_rollback.assert_called_once_with()

    def test_background_service_lock_helpers_allow_missing_fcntl(self, app):
        """Lock helpers should remain usable when fcntl is unavailable."""
        from backend import background_services

        with app.app_context(), patch.object(background_services, "fcntl", None):
            lock_path = background_services._background_service_lock_path(app)
            lock_handle = background_services._acquire_background_service_process_lock(
                app
            )
            assert lock_handle is not None
            assert lock_handle.closed is False

            background_services._release_background_service_process_lock(lock_handle)
            assert lock_handle.closed is True

        lock_path.unlink(missing_ok=True)
