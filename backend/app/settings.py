from dataclasses import dataclass
import os
from pathlib import Path

DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    """Runtime configuration.

    Each field is an explicit override (used by tests). When a field is
    ``None`` the matching ``resolved_*`` accessor falls back to an
    environment variable, then to a sensible default.
    """

    database_url: str | None = None
    project_root: Path | None = None
    data_dir: Path | None = None
    output_dir: Path | None = None
    web_dist_dir: Path | None = None
    cors_origins: tuple[str, ...] | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    auth_password: str | None = None
    render_timeout_sec: float | None = None
    require_audio: bool | None = None

    # ── paths ────────────────────────────────────────────────────────────
    def resolved_project_root(self) -> Path:
        if self.project_root:
            return Path(self.project_root)
        env = _env("PROJECT_ROOT")
        if env:
            return Path(env)
        return Path(__file__).resolve().parents[2]

    def resolved_data_dir(self) -> Path:
        if self.data_dir:
            return Path(self.data_dir)
        env = _env("DATA_DIR")
        if env:
            return Path(env)
        return Path(__file__).resolve().parents[1] / "data"

    def resolved_output_dir(self) -> Path:
        if self.output_dir:
            return Path(self.output_dir)
        env = _env("OUTPUT_DIR")
        if env:
            return Path(env)
        return self.resolved_project_root() / "out"

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        env = _env("DATABASE_URL")
        if env:
            return env
        db_path = self.resolved_data_dir() / "cpe_video.db"
        return f"sqlite+aiosqlite:///{db_path}"

    def resolved_web_dist_dir(self) -> Path | None:
        if self.web_dist_dir:
            return Path(self.web_dist_dir)
        env = _env("WEB_DIST_DIR")
        if env:
            return Path(env)
        return self.resolved_project_root() / "web" / "dist"

    # ── cors ─────────────────────────────────────────────────────────────
    def resolved_cors_origins(self) -> tuple[str, ...]:
        if self.cors_origins is not None:
            return tuple(self.cors_origins)
        env = _env("CORS_ORIGINS")
        if env:
            return tuple(origin.strip() for origin in env.split(",") if origin.strip())
        return DEFAULT_CORS_ORIGINS

    # ── openai ───────────────────────────────────────────────────────────
    def resolved_openai_api_key(self) -> str | None:
        return self.openai_api_key or _env("OPENAI_API_KEY")

    def resolved_openai_model(self) -> str:
        return self.openai_model or _env("OPENAI_MODEL") or "gpt-5.6-luna"

    # ── auth ─────────────────────────────────────────────────────────────
    def resolved_auth_password(self) -> str | None:
        return self.auth_password or _env("AUTH_PASSWORD")

    # ── render ───────────────────────────────────────────────────────────
    def resolved_render_timeout_sec(self) -> float:
        if self.render_timeout_sec is not None:
            return self.render_timeout_sec
        env = _env("RENDER_TIMEOUT_SEC")
        if env:
            try:
                return float(env)
            except ValueError:
                pass
        return 1800.0

    def resolved_require_audio(self) -> bool:
        if self.require_audio is not None:
            return self.require_audio
        env = _env("RENDER_REQUIRE_AUDIO")
        return env is not None and env.lower() in {"1", "true", "yes"}
