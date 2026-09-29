from fastapi import APIRouter, HTTPException, Request, status

from app.db import SessionDep
from app.schemas import (
    DraftCheckIssue,
    DraftCheckRequest,
    DraftCheckResponse,
    GenerateDraftRequest,
    JobResponse,
    ProblemStatementRequest,
    ProblemStatementResponse,
)
from app.services.generation_service import GeneratorProvider, validate_draft
from app.services.job_service import save_generated_job
from app.services.problem_service import ProblemFetchError, fetch_uva_pdf

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
            with_animation=payload.withAnimation,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return await save_generated_job(session, draft.job_name, draft.steps)


@router.post("/problem-statement", response_model=ProblemStatementResponse)
async def problem_statement(
    payload: ProblemStatementRequest, request: Request
) -> ProblemStatementResponse:
    provider: GeneratorProvider = request.app.state.generation_provider
    try:
        pdf = await fetch_uva_pdf(payload.uvaId)
    except ProblemFetchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    try:
        text = await provider.summarize_problem(pdf, payload.uvaId)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return ProblemStatementResponse(uvaId=payload.uvaId, problemStatement=text)


@router.post("/drafts/check", response_model=DraftCheckResponse)
async def check_draft(payload: DraftCheckRequest, request: Request) -> DraftCheckResponse:
    issues = [
        DraftCheckIssue(stepIndex=i.step_index, level=i.level, message=i.message, source="rule")
        for i in validate_draft(payload.steps, None)
    ]
    if payload.ai:
        provider: GeneratorProvider = request.app.state.generation_provider
        try:
            reviewed = await provider.review_draft(payload.steps)
        except RuntimeError as exc:
            # AI review is advisory: keep the rule results and say why it's missing.
            issues.append(DraftCheckIssue(stepIndex=None, level="warning", message=f"AI 審稿失敗：{exc}", source="ai"))
        else:
            issues += [
                DraftCheckIssue(stepIndex=i.step_index, level=i.level, message=i.message, source="ai")
                for i in reviewed
            ]
    return DraftCheckResponse(issues=issues)
