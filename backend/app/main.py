from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.auth import require_auth
from app.auth import router as auth_router
from app.db import build_sessionmaker, close_sessionmaker, init_db
from app.routers import generation, jobs, render_jobs
from app.services.generation_service import build_generation_provider
from app.services.render_service import cleanup_orphan_render_jobs
from app.settings import Settings


def _materialize_gcp_credentials(settings: Settings) -> None:
    """Allow GCP creds to be supplied as JSON via env (cloud-friendly).

    ``gen-audio.mjs`` expects ``GOOGLE_APPLICATION_CREDENTIALS`` to be a file
    path. On platforms where mounting a key file is awkward, set
    ``GOOGLE_APPLICATION_CREDENTIALS_JSON`` instead and we write it to disk.
    """
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not raw:
        return
    existing = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if existing and Path(existing).exists():
        return
    data_dir = settings.resolved_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    creds_path = data_dir / "gcp-credentials.json"
    creds_path.write_text(raw, encoding="utf-8")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)


def _ensure_storage_dirs(settings: Settings) -> None:
    """Create data/output dirs (and the SQLite parent) before first use.

    On a fresh volume (e.g. Zeabur ``DATA_DIR=/data/db``) the directory does not
    exist yet, and SQLite cannot create the file inside a missing folder.
    """
    settings.resolved_data_dir().mkdir(parents=True, exist_ok=True)
    settings.resolved_output_dir().mkdir(parents=True, exist_ok=True)
    url = settings.resolved_database_url()
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        Path(url[len(prefix):]).parent.mkdir(parents=True, exist_ok=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Load a local .env for development; real env vars (e.g. Zeabur
        # dashboard) take precedence and are untouched.
        load_dotenv(resolved_settings.resolved_project_root() / ".env", override=False)
        _materialize_gcp_credentials(resolved_settings)
        _ensure_storage_dirs(resolved_settings)
        sessionmaker = build_sessionmaker(resolved_settings.resolved_database_url())
        app.state.sessionmaker = sessionmaker
        app.state.settings = resolved_settings
        app.state.generation_provider = build_generation_provider(resolved_settings)
        await init_db(sessionmaker)
        await cleanup_orphan_render_jobs(sessionmaker, resolved_settings.resolved_project_root())
        yield
        await close_sessionmaker(sessionmaker)

    # When a shared password is configured, hide the OpenAPI schema / docs so
    # the API surface isn't exposed unauthenticated.
    docs_enabled = not resolved_settings.resolved_auth_password()
    app = FastAPI(
        title="CPE Video API",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.resolved_cors_origins()),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    auth_dep = [Depends(require_auth)]
    app.include_router(auth_router)
    app.include_router(jobs.router, dependencies=auth_dep)
    app.include_router(generation.router, dependencies=auth_dep)
    app.include_router(render_jobs.router, dependencies=auth_dep)

    _mount_frontend(app, resolved_settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built web editor (Vite ``dist``) with SPA fallback.

    Registered last so ``/api/*`` and ``/health`` always win. Unknown
    client-side routes fall back to ``index.html`` so deep links survive a
    refresh; path traversal outside ``dist`` is rejected.
    """
    dist = settings.resolved_web_dist_dir()
    if not dist or not dist.exists():
        return
    index_file = dist / "index.html"
    if not index_file.exists():
        return
    dist_root = dist.resolve()

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/") or full_path == "health":
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (dist_root / full_path).resolve()
        if full_path and candidate.is_file() and dist_root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
