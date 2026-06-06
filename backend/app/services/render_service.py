import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models import RenderJobModel
from app.schemas import JobResponse
from app.services.job_service import now_ms, require_job
from app.settings import Settings

logger = logging.getLogger(__name__)

AUDIO_TIMEOUT_SEC = 600.0


def normalize_folder_name(folder_name: str | None, fallback: str) -> str:
    base = (folder_name or fallback).strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", base).strip("-")
    return normalized or "untitled"


def build_render_files(job: JobResponse, folder_name: str | None) -> tuple[str, str, dict[str, str]]:
    normalized = normalize_folder_name(folder_name, job.name)
    cpp_files: dict[str, str] = {}
    config_steps = []
    for step in job.steps:
        existing = cpp_files.get(step.fileLabel)
        if existing is not None and existing != step.fileContent:
            raise ValueError(f"同一個 cpp 檔名有不同內容：{step.fileLabel}。請改用不同檔名或讓內容一致。")
        cpp_files[step.fileLabel] = step.fileContent
        raw = step.model_dump(by_alias=True, exclude_none=True)
        raw["file"] = raw.pop("fileLabel")
        raw.pop("fileContent")
        config_steps.append(raw)
    return normalized, json.dumps({"steps": config_steps}, ensure_ascii=False, indent=2), cpp_files


async def create_render_job(
    session: AsyncSession,
    job_id: str,
    folder_name: str | None,
) -> RenderJobModel:
    job = await require_job(session, job_id)
    if not job.steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job must contain at least one step")
    build_render_files(job, folder_name)
    timestamp = now_ms()
    model = RenderJobModel(
        id=str(uuid.uuid4()),
        job_id=job_id,
        status="queued",
        error=None,
        output_path=None,
        output_filename=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model


async def get_render_job(session: AsyncSession, render_job_id: str) -> RenderJobModel | None:
    return await session.get(RenderJobModel, render_job_id)


async def require_render_job(session: AsyncSession, render_job_id: str) -> RenderJobModel:
    model = await get_render_job(session, render_job_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found")
    return model


def _audio_credentials_available() -> bool:
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    return bool(creds) and Path(creds).exists()


async def _generate_audio(project_root: Path, render_folder: str, require_audio: bool) -> None:
    """Generate per-step narration into ``public/<render_folder>/audio`` by
    reusing the existing ``scripts/gen-audio.mjs`` CLI.

    When credentials are missing or generation fails we fall back to a silent
    render — unless ``require_audio`` is set, in which case we raise.
    """
    if not _audio_credentials_available():
        if require_audio:
            raise RuntimeError("需要語音，但未設定 GOOGLE_APPLICATION_CREDENTIALS 金鑰檔。")
        logger.warning("Audio skipped: GOOGLE_APPLICATION_CREDENTIALS not configured; rendering silent video.")
        return

    proc = await asyncio.create_subprocess_exec(
        "node",
        "scripts/gen-audio.mjs",
        render_folder,
        cwd=project_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=AUDIO_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        if require_audio:
            raise RuntimeError("語音產生逾時。")
        logger.warning("Audio generation timed out; rendering silent video.")
        return

    if proc.returncode != 0:
        message = stderr.decode().strip() or f"gen-audio exited with code {proc.returncode}"
        if require_audio:
            raise RuntimeError(f"語音產生失敗：{message}")
        logger.warning("Audio generation failed; rendering silent video: %s", message)


async def run_render_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    render_job_id: str,
    folder_name: str | None,
) -> None:
    project_root = settings.resolved_project_root()
    output_dir = settings.resolved_output_dir()
    render_timeout = settings.resolved_render_timeout_sec()
    require_audio = settings.resolved_require_audio()

    async with sessionmaker() as session:
        model = await require_render_job(session, render_job_id)
        model.status = "running"
        model.updated_at = now_ms()
        await session.commit()

        public_folder: Path | None = None
        output_path: Path | None = None
        try:
            job = await require_job(session, model.job_id)
            normalized, config_json, cpp_files = build_render_files(job, folder_name)
            render_folder = f"__render_{normalized}_{model.id[:8]}"
            public_folder = project_root / "public" / render_folder
            output_path = output_dir / f"{render_folder}.mp4"

            public_folder.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            (public_folder / "config.json").write_text(config_json, encoding="utf-8")
            for filename, content in cpp_files.items():
                (public_folder / filename).write_text(content, encoding="utf-8")

            await _generate_audio(project_root, render_folder, require_audio)

            proc = await asyncio.create_subprocess_exec(
                "npx",
                "remotion",
                "render",
                "src/index.ts",
                "Main",
                str(output_path),
                "--props",
                json.dumps({"folder": render_folder}),
                "--overwrite",
                cwd=project_root,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=render_timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError(f"Render 逾時（超過 {int(render_timeout)} 秒）。")

            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip() or f"Remotion render failed with code {proc.returncode}")

            model.status = "succeeded"
            model.output_path = str(output_path)
            model.output_filename = f"{normalized}.mp4"
            model.error = None
        except Exception as exc:  # noqa: BLE001 — recorded on the render job for the client
            model.status = "failed"
            model.error = str(exc)
        finally:
            if public_folder is not None:
                shutil.rmtree(public_folder, ignore_errors=True)
            if model.status == "failed" and output_path is not None and output_path.exists():
                output_path.unlink(missing_ok=True)
            model.updated_at = now_ms()
            await session.commit()


async def cleanup_orphan_render_jobs(sessionmaker: async_sessionmaker[AsyncSession], project_root: Path) -> None:
    """On startup, fail render jobs left ``queued``/``running`` by a previous
    process (they cannot resume) and remove stale ``public/__render_*`` dirs.
    """
    async with sessionmaker() as session:
        result = await session.execute(
            select(RenderJobModel).where(RenderJobModel.status.in_(("queued", "running")))
        )
        orphans = result.scalars().all()
        for model in orphans:
            model.status = "failed"
            model.error = "Render job interrupted by a server restart."
            model.updated_at = now_ms()
        if orphans:
            await session.commit()
            logger.info("Marked %d interrupted render job(s) as failed.", len(orphans))

    public_dir = project_root / "public"
    if public_dir.exists():
        for path in public_dir.glob("__render_*"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
