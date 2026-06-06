from fastapi import APIRouter, HTTPException, Request, status

from app.db import SessionDep
from app.schemas import GenerateDraftRequest, JobResponse
from app.services.generation_service import GeneratorProvider
from app.services.job_service import save_generated_job

router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/generate-draft", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    payload: GenerateDraftRequest, session: SessionDep, request: Request
) -> JobResponse:
    provider: GeneratorProvider = request.app.state.generation_provider
    try:
        draft = await provider.generate(
            name=payload.name,
            problem_statement=payload.problemStatement,
            solution_code=payload.solutionCode,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return await save_generated_job(session, draft.job_name, draft.steps)
