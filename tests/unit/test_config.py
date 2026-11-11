from app.core.config import Settings


def test_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "abc")
    s = Settings(_env_file=None)
    assert s.timezone == "Asia/Tehran"
    assert s.internal_service_token.get_secret_value() == "abc"


def test_secret_is_not_printed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "super-secret")
    s = Settings(_env_file=None)
    assert "super-secret" not in repr(s)
