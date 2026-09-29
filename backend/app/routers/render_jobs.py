from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.db import SessionDep
from app.models import RenderJobModel
from app.schemas import RenderJobCreateRequest, RenderJobCreateResponse, RenderJobResponse
from app.services.render_service import create_render_job, require_render_job, run_render_job

router = APIRouter(prefix="/api/render-jobs", tags=["render-jobs"])


def render_job_response(model: RenderJobModel) -> RenderJobResponse:
    return RenderJobResponse(
        id=model.id,
        jobId=model.job_id,
        status=model.status,  # type: ignore[arg-type]
        progress=1.0 if model.status == "succeeded" else None,
        error=model.error,
        outputFilename=model.output_filename,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )


@router.post("", response_model=RenderJobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: RenderJobCreateRequest,
    session: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RenderJobCreateResponse:
    model = await create_render_job(session, payload.jobId, payload.folderName)
    background_tasks.add_task(
        run_render_job,
        request.app.state.sessionmaker,
        request.app.state.settings,
        model.id,
        payload.folderName,
    )
    return RenderJobCreateResponse(id=model.id, status="queued")


@router.get("/{render_job_id}", response_model=RenderJobResponse)
async def get(render_job_id: str, session: SessionDep) -> RenderJobResponse:
    return render_job_response(await require_render_job(session, render_job_id))


@router.get("/{render_job_id}/download")
async def download(render_job_id: str, session: SessionDep) -> FileResponse:
    model = await require_render_job(session, render_job_id)
    if model.status != "succeeded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Render job is not complete")
    if not model.output_path or not Path(model.output_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered file not found")
    return FileResponse(
        model.output_path,
        media_type="video/mp4",
        filename=model.output_filename or f"{model.id}.mp4",
    )
