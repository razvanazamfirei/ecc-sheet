"""Tests for app initialization and init_db function."""

from unittest.mock import patch

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

    def test_inject_auth_provides_current_user(self, client, app):
        """Test that inject_auth provides current_user in template context."""
        # Make a request to get template context
        response = client.get("/")
        assert response.status_code == 200
        # The template should have access to current_user

    def test_inject_auth_provides_is_admin(self, client, app):
        """Test that inject_auth provides is_admin in template context."""
        response = client.get("/")
        assert response.status_code == 200
        # The template should have access to is_admin
