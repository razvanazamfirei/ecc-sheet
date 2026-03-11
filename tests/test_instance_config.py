import json
from importlib import reload
from unittest.mock import mock_open, patch

import pytest

from backend import instance_config


class TestInstanceConfig:
    def test_missing_file_raises_error(self):
        """Test that a missing instance_settings.json raises a RuntimeError."""
        with patch("pathlib.Path.open", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError) as exc_info:
                reload(instance_config)

            assert "Failed to load required instance settings" in str(exc_info.value)
            assert "This file must exist" in str(exc_info.value)

    def test_malformed_json_raises_error(self):
        """Test that an invalid instance_settings.json raises a RuntimeError."""
        with patch(
            "pathlib.Path.open", side_effect=json.JSONDecodeError("msg", "doc", 0)
        ):
            with pytest.raises(RuntimeError) as exc_info:
                reload(instance_config)

            assert "Failed to load required instance settings" in str(exc_info.value)

    def test_valid_json_parsing(self):
        """Test parsing valid JSON with role flag derivation."""
        mock_data = {
            "default_cutoff_hour": 18,
            "default_cutoff_minute": 0,
            "roles": [
                {
                    "name": "ECA 1",
                    "display_order": 1,
                    "is_backup": False,
                    "is_call_team": False,
                    "cutoff_hour": 16,
                    "cutoff_minute": 45,
                    "is_late_role": False,
                    "is_weekday_backup": False,
                    "is_schedule_importable": True,
                },
                {
                    "name": "Backup",
                    "is_backup": True,
                    "is_weekday_backup": True,
                    "is_schedule_importable": True,
                },
                {
                    "name": "Late Role",
                    "is_late_role": True,
                    "is_schedule_importable": False,
                },
                {
                    "name": "First Call",
                    "is_call_team": True,
                    "is_schedule_importable": False,
                },
            ],
        }

        # Mock the open call to return our valid JSON
        with patch("pathlib.Path.open", mock_open(read_data=json.dumps(mock_data))):
            reload(instance_config)

            assert instance_config.DEFAULT_CUTOFF_HOUR == 18
            assert instance_config.DEFAULT_CUTOFF_MINUTE == 0

            # Test derivations
            assert "ECA 1" in instance_config.SCHEDULE_ROLE_NAMES
            assert "Backup" in instance_config.BACKUP_ROLE_NAMES
            assert "Backup" in instance_config.WEEKDAY_BACKUP_ROLE_NAMES
            assert "Late Role" in instance_config.LATE_ROLE_NAMES
            assert "First Call" in instance_config.CALL_TEAM_ROLE_NAMES

            # Test cutoff maps
            assert instance_config.ROLE_CUTOFF_HOURS["ECA 1"] == 16
            assert instance_config.ROLE_CUTOFF_MINUTES["ECA 1"] == 45

            # Test get_role_definitions returns deep copies
            roles = instance_config.get_role_definitions()
            assert len(roles) == 4

            # Mutate the copy
            roles[0]["name"] = "Mutated"

            # Request again and ensure it's not mutated
            roles_again = instance_config.get_role_definitions()
            assert roles_again[0]["name"] == "ECA 1"
