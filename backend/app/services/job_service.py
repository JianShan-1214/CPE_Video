import json
import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobModel
from app.schemas import DraftStep, ImportJobRequest, JobResponse, JobUpdateRequest


def now_ms() -> int:
    return int(time.time() * 1000)


def job_from_model(model: JobModel) -> JobResponse:
    return JobResponse(
        id=model.id,
        name=model.name,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
        theme=model.theme,
        width=json.loads(model.width_json),
        steps=json.loads(model.steps_json),
    )


async def list_jobs(session: AsyncSession) -> list[JobResponse]:
    result = await session.execute(select(JobModel).order_by(JobModel.updated_at.desc()))
    return [job_from_model(model) for model in result.scalars().all()]


async def get_job(session: AsyncSession, job_id: str) -> JobResponse | None:
    model = await session.get(JobModel, job_id)
    return job_from_model(model) if model else None


async def require_job(session: AsyncSession, job_id: str) -> JobResponse:
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def create_empty_job(session: AsyncSession, name: str | None = None) -> JobResponse:
    timestamp = now_ms()
    model = JobModel(
        id=str(uuid.uuid4()),
        name=name or "Untitled Job",
        theme="github-dark",
        width_json=json.dumps({"type": "fixed", "value": 1920}),
        steps_json="[]",
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(model)
    await session.commit()
    return job_from_model(model)


async def save_generated_job(
    session: AsyncSession,
    name: str,
    steps: list[DraftStep],
) -> JobResponse:
    timestamp = now_ms()
    model = JobModel(
        id=str(uuid.uuid4()),
        name=name,
        theme="github-dark",
        width_json=json.dumps({"type": "fixed", "value": 1920}),
        steps_json=json.dumps([step.model_dump(by_alias=True, exclude_none=True) for step in steps]),
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(model)
    await session.commit()
    return job_from_model(model)


async def update_job(
    session: AsyncSession,
    job_id: str,
    payload: JobUpdateRequest,
) -> JobResponse:
    model = await session.get(JobModel, job_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    model.name = payload.name
    model.theme = payload.theme
    model.width_json = json.dumps(payload.width.model_dump())
    model.steps_json = json.dumps(
        [step.model_dump(by_alias=True, exclude_none=True) for step in payload.steps],
    )
    model.updated_at = now_ms()
    await session.commit()
    await session.refresh(model)
    return job_from_model(model)


async def delete_job(session: AsyncSession, job_id: str) -> None:
    model = await session.get(JobModel, job_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    await session.delete(model)
    await session.commit()


async def import_job(session: AsyncSession, payload: ImportJobRequest) -> JobResponse:
    try:
        config = json.loads(payload.configJson)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"config.json 解析失敗：{exc}") from exc

    raw_steps = config.get("steps")
    if not isinstance(raw_steps, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="config.json 必須包含 steps 陣列")

    steps: list[DraftStep] = []
    missing: list[str] = []
    for raw in raw_steps:
        file_name = raw.get("file") if isinstance(raw, dict) else None
        if not isinstance(file_name, str) or file_name not in payload.cppFiles:
            if isinstance(file_name, str):
                missing.append(file_name)
            continue
        steps.append(
            DraftStep.model_validate(
                {
                    "label": raw.get("label", ""),
                    "from": raw.get("from", 0),
                    "to": raw.get("to", 0),
                    "fileLabel": file_name,
                    "fileContent": payload.cppFiles[file_name],
                    "subtitle": raw.get("subtitle", ""),
                    "focusLine": raw.get("focusLine"),
                    "highlight": raw.get("highlight"),
                    "annotations": raw.get("annotations"),
                },
            ),
        )

    if missing:
        unique = ", ".join(dict.fromkeys(missing))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"找不到 cpp 檔：{unique}。請一併上傳這些檔案。")

    return await save_generated_job(session, payload.name or "Imported Job", steps)
