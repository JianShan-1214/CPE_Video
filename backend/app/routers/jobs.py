from fastapi import APIRouter, Response, status

from app.db import SessionDep
from app.schemas import ImportJobRequest, JobCreateRequest, JobResponse, JobUpdateRequest
from app.services import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(session: SessionDep) -> list[JobResponse]:
    return await job_service.list_jobs(session)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobCreateRequest, session: SessionDep) -> JobResponse:
    return await job_service.create_empty_job(session, payload.name)


@router.post("/import", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def import_job(payload: ImportJobRequest, session: SessionDep) -> JobResponse:
    return await job_service.import_job(session, payload)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, session: SessionDep) -> JobResponse:
    return await job_service.require_job(session, job_id)


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, payload: JobUpdateRequest, session: SessionDep) -> JobResponse:
    return await job_service.update_job(session, job_id, payload)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, session: SessionDep) -> Response:
    await job_service.delete_job(session, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
