import pytest

_HERMETIC_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "AUTH_PASSWORD",
    "CORS_ORIGINS",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_APPLICATION_CREDENTIALS_JSON",
    "DATABASE_URL",
    "DATA_DIR",
    "OUTPUT_DIR",
    "WEB_DIST_DIR",
    "PROJECT_ROOT",
    "RENDER_REQUIRE_AUDIO",
    "RENDER_TIMEOUT_SEC",
)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Keep every test deterministic regardless of the developer's shell."""
    for name in _HERMETIC_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
