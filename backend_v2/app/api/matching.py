"""
Matching API endpoints — explicit match triggers and explanation.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db
from app.models.candidate import Candidate, CandidateCV
from app.models.job_application import JobApplication
from app.models.match import MatchResult
from app.schemas.matching import (
    MatchRequest,
    MatchResultResponse,
    ScoreBreakdown,
    MatchExplanation,
    MatchExplainResponse,
    CandidateToJobsResponse,
    JobToCandidatesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/match", tags=["matching"])


class JobFindTalentMatchResponse(MatchResultResponse):
    source_cv_id: int | None = None


class JobFindTalentResponse(BaseModel):
    job_id: int
    source_job_id: int | None = None
    matches: list[JobFindTalentMatchResponse]
    total: int


class JobRankApplicantsMatchResponse(MatchResultResponse):
    source_cv_id: int | None = None


class JobRankApplicantsResponse(BaseModel):
    job_id: int
    source_job_id: int | None = None
    matches: list[JobRankApplicantsMatchResponse]
    total: int


@router.post("/candidate-to-jobs/{candidate_id}", response_model=CandidateToJobsResponse)
async def match_candidate_to_jobs(
    candidate_id: int,
    body: MatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Find best job matches for a candidate."""
    from app.services.matching_service import MatchingService

    req = body or MatchRequest()
    svc = MatchingService(db)
    try:
        matches = await svc.match_candidate_to_jobs(
            candidate_id, top_k=req.top_k, min_score=req.min_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    source_candidate_map = await _build_source_candidate_map(db, matches)
    source_application_map = await _build_source_application_map(db, matches)

    return CandidateToJobsResponse(
        candidate_id=candidate_id,
        total=len(matches),
        matches=[_to_response(m, source_candidate_map, source_application_map) for m in matches],
    )


@router.post("/job-rank-applicants/{source_job_id}", response_model=JobRankApplicantsResponse)
async def rank_job_applicants(
    source_job_id: int,
    body: MatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Rank applicants for a job using the exact CV attached to each application."""
    from app.services.matching_service import MatchingService

    req = body or MatchRequest()
    svc = MatchingService(db)
    try:
        job, matches = await svc.rank_job_applicants_by_source_job_id(
            source_job_id, top_k=req.top_k, min_score=req.min_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    source_candidate_map = await _build_source_candidate_map(db, matches)
    source_application_map = await _build_source_application_map(db, matches)
    source_cv_map = await _build_source_cv_map(db, matches)

    return JobRankApplicantsResponse(
        job_id=job.id,
        source_job_id=job.source_job_id,
        total=len(matches),
        matches=[
            _to_job_rank_applicants_response(
                m,
                source_candidate_map,
                source_application_map,
                source_cv_map,
            )
            for m in matches
        ],
    )


@router.post("/job-find-talent/{source_job_id}", response_model=JobFindTalentResponse)
async def job_find_talent(
    source_job_id: int,
    body: MatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search the talent pool using searchable CVs from open-to-work candidates only."""
    from app.services.matching_service import MatchingService

    req = body or MatchRequest()
    svc = MatchingService(db)
    try:
        job, matches = await svc.find_talent_for_job_by_source_job_id(
            source_job_id, top_k=req.top_k, min_score=req.min_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    source_candidate_map = await _build_source_candidate_map(db, matches)
    source_application_map = await _build_source_application_map(db, matches)
    source_cv_map = await _build_source_cv_map(db, matches)

    return JobFindTalentResponse(
        job_id=job.id,
        source_job_id=job.source_job_id,
        total=len(matches),
        matches=[
            _to_job_find_talent_response(
                m,
                source_candidate_map,
                source_application_map,
                source_cv_map,
            )
            for m in matches
        ],
    )


@router.post("/job-to-candidates/{job_id}", response_model=JobToCandidatesResponse)
async def match_job_to_candidates(
    job_id: int,
    body: MatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Backward-compatible alias for applicant ranking."""
    from app.services.matching_service import MatchingService

    req = body or MatchRequest()
    svc = MatchingService(db)
    try:
        matches = await svc.rank_job_applicants(
            job_id, top_k=req.top_k, min_score=req.min_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    source_candidate_map = await _build_source_candidate_map(db, matches)
    source_application_map = await _build_source_application_map(db, matches)

    return JobToCandidatesResponse(
        job_id=job_id,
        total=len(matches),
        matches=[_to_response(m, source_candidate_map, source_application_map) for m in matches],
    )


@router.post("/job-to-all-candidates/{job_id}", response_model=JobToCandidatesResponse)
async def match_job_to_all_candidates(
    job_id: int,
    body: MatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Backward-compatible alias for talent search."""
    from app.services.matching_service import MatchingService

    req = body or MatchRequest()
    svc = MatchingService(db)
    try:
        matches = await svc.find_talent_for_job(
            job_id, top_k=req.top_k, min_score=req.min_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    source_candidate_map = await _build_source_candidate_map(db, matches)
    source_application_map = await _build_source_application_map(db, matches)

    return JobToCandidatesResponse(
        job_id=job_id,
        total=len(matches),
        matches=[_to_response(m, source_candidate_map, source_application_map) for m in matches],
    )


@router.get("/explain/{match_id}", response_model=MatchExplainResponse)
async def explain_match(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed explanation of a match."""
    result = await db.execute(
        select(MatchResult).where(MatchResult.id == match_id)
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    source_candidate_map = await _build_source_candidate_map(db, [match])
    source_application_map = await _build_source_application_map(db, [match])

    # Parse explanation string into structured format
    parts = (match.explanation or "").split(" | ")
    exp_fit = ""
    sal_fit = ""
    loc_fit = ""
    for p in parts:
        if p.startswith("Experience:"):
            exp_fit = p
        elif p.startswith("Salary"):
            sal_fit = p
        elif p.startswith("Location:"):
            loc_fit = p

    return MatchExplainResponse(
        match_id=match.id,
        mode=match.mode,
        candidate_id=match.candidate_id,
        source_candidate_id=source_candidate_map.get(match.candidate_id),
        job_id=match.job_id,
        candidate_cv_id=match.candidate_cv_id,
        application_id=match.application_id,
        source_application_id=source_application_map.get(match.application_id),
        overall_score=match.overall_score,
        scores=ScoreBreakdown(
            semantic_score=match.semantic_score,
            skill_match_score=match.skill_match_score,
            experience_score=match.experience_score,
            location_score=match.location_score,
            salary_score=match.salary_score,
        ),
        explanation=MatchExplanation(
            matched_skills=match.matched_skills or [],
            missing_skills=match.missing_skills or [],
            experience_fit=exp_fit,
            salary_fit=sal_fit,
            location_fit=loc_fit,
        ),
    )


@router.get("/history/{candidate_id}")
async def match_history(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all past match results for a candidate."""
    result = await db.execute(
        select(MatchResult)
        .where(MatchResult.candidate_id == candidate_id)
        .order_by(MatchResult.overall_score.desc())
    )
    matches = result.scalars().all()
    source_candidate_map = await _build_source_candidate_map(db, matches)
    source_application_map = await _build_source_application_map(db, matches)
    return {
        "candidate_id": candidate_id,
        "total": len(matches),
        "matches": [_to_response(m, source_candidate_map, source_application_map) for m in matches],
    }


async def _build_source_candidate_map(
    db: AsyncSession,
    matches: list[MatchResult],
) -> dict[int, int | None]:
    candidate_ids = {match.candidate_id for match in matches}
    if not candidate_ids:
        return {}

    result = await db.execute(
        select(Candidate.id, Candidate.source_candidate_id).where(
            Candidate.id.in_(candidate_ids)
        )
    )
    return {candidate_id: source_candidate_id for candidate_id, source_candidate_id in result}


async def _build_source_application_map(
    db: AsyncSession,
    matches: list[MatchResult],
) -> dict[int, int | None]:
    application_ids = {
        match.application_id for match in matches if match.application_id is not None
    }
    if not application_ids:
        return {}

    result = await db.execute(
        select(JobApplication.id, JobApplication.source_application_id).where(
            JobApplication.id.in_(application_ids)
        )
    )
    return {
        application_id: source_application_id
        for application_id, source_application_id in result
    }


async def _build_source_cv_map(
    db: AsyncSession,
    matches: list[MatchResult],
) -> dict[int, int | None]:
    cv_ids = {
        match.candidate_cv_id
        for match in matches
        if match.candidate_cv_id is not None
    }
    if not cv_ids:
        return {}

    result = await db.execute(
        select(CandidateCV.id, CandidateCV.source_cv_id).where(
            CandidateCV.id.in_(cv_ids)
        )
    )
    return {cv_id: source_cv_id for cv_id, source_cv_id in result}


def _to_job_find_talent_response(
    m: MatchResult,
    source_candidate_map: dict[int, int | None] | None = None,
    source_application_map: dict[int, int | None] | None = None,
    source_cv_map: dict[int, int | None] | None = None,
) -> JobFindTalentMatchResponse:
    return JobFindTalentMatchResponse(
        **_to_response(m, source_candidate_map, source_application_map).model_dump(),
        source_cv_id=(source_cv_map or {}).get(m.candidate_cv_id),
    )


def _to_job_rank_applicants_response(
    m: MatchResult,
    source_candidate_map: dict[int, int | None] | None = None,
    source_application_map: dict[int, int | None] | None = None,
    source_cv_map: dict[int, int | None] | None = None,
) -> JobRankApplicantsMatchResponse:
    return JobRankApplicantsMatchResponse(
        **_to_response(m, source_candidate_map, source_application_map).model_dump(),
        source_cv_id=(source_cv_map or {}).get(m.candidate_cv_id),
    )


def _to_response(
    m: MatchResult,
    source_candidate_map: dict[int, int | None] | None = None,
    source_application_map: dict[int, int | None] | None = None,
) -> MatchResultResponse:
    return MatchResultResponse(
        id=m.id,
        mode=m.mode,
        candidate_id=m.candidate_id,
        source_candidate_id=(source_candidate_map or {}).get(m.candidate_id),
        job_id=m.job_id,
        candidate_cv_id=m.candidate_cv_id,
        application_id=m.application_id,
        source_application_id=(source_application_map or {}).get(m.application_id),
        overall_score=m.overall_score,
        scores=ScoreBreakdown(
            semantic_score=m.semantic_score,
            skill_match_score=m.skill_match_score,
            experience_score=m.experience_score,
            location_score=m.location_score,
            salary_score=m.salary_score,
        ),
        matched_skills=m.matched_skills,
        missing_skills=m.missing_skills,
        explanation=m.explanation,
        status=m.status,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
