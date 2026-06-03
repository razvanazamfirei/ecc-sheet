from backend.env_utils import env_csv, env_flag, env_int, env_str


def test_env_flag_parses_truthy_values_and_defaults(monkeypatch) -> None:
    monkeypatch.delenv("FEATURE_ENABLED", raising=False)
    assert env_flag("FEATURE_ENABLED") is False
    assert env_flag("FEATURE_ENABLED", default=True) is True

    monkeypatch.setenv("FEATURE_ENABLED", " yes ")
    assert env_flag("FEATURE_ENABLED") is True

    monkeypatch.setenv("FEATURE_ENABLED", "false")
    assert env_flag("FEATURE_ENABLED") is False


def test_env_int_preserves_zero_and_uses_defaults_for_blank_or_invalid(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ZERO_VALUE", "0")
    monkeypatch.setenv("INVALID_VALUE", "not-an-int")
    monkeypatch.setenv("BLANK_VALUE", "  ")
    monkeypatch.delenv("MISSING_VALUE", raising=False)

    assert env_int("ZERO_VALUE", 8) == 0
    assert env_int("INVALID_VALUE", 8) == 8
    assert env_int("BLANK_VALUE", 8) == 8
    assert env_int("MISSING_VALUE", 8) == 8
    assert env_int("INVALID_VALUE") is None


def test_env_str_trims_and_defaults_for_blank_or_missing_values(monkeypatch) -> None:
    monkeypatch.setenv("NAME", "  Admin  ")
    monkeypatch.setenv("BLANK_NAME", "  ")
    monkeypatch.delenv("MISSING_NAME", raising=False)

    assert env_str("NAME") == "Admin"
    assert env_str("BLANK_NAME", "Default") == "Default"
    assert env_str("MISSING_NAME", "Default") == "Default"
    assert env_str("BLANK_NAME") is None


def test_env_csv_trims_values_and_uses_default_only_when_missing(monkeypatch) -> None:
    monkeypatch.setenv("NAMES", " Admin, , Test User ")
    monkeypatch.setenv("BLANK_NAMES", "")
    monkeypatch.delenv("MISSING_NAMES", raising=False)

    assert env_csv("NAMES") == ["Admin", "Test User"]
    assert env_csv("BLANK_NAMES", "Fallback") == []
    assert env_csv("MISSING_NAMES", "Admin, Test User") == [
        "Admin",
        "Test User",
    ]
