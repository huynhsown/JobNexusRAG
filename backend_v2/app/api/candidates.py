"""
Candidate & CV API endpoints.
"""
from __future__ import annotations

import os
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import get_db
from app.models.candidate import Candidate, CandidateCV, CandidateStatus, CVStatus
from app.schemas.candidate import (
    CandidateCreate,
    CandidateUpdate,
    CandidateResponse,
    CandidateDetailResponse,
    CVResponse,
    CVProcessResponse,
    CVUploadResponse,
)
from app.services.candidate_reference_service import (
    CandidateCVMismatchError,
    CandidateReferenceService,
    SourceCandidateNotFoundError,
    SourceCVNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])

UPLOAD_DIR = settings.BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 50 * 1024 * 1024


# ------------------------------------------------------------------
# Candidate CRUD
# ------------------------------------------------------------------

@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    body: CandidateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new candidate profile."""
    candidate = Candidate(
        name=body.name,
        email=body.email,
        phone=body.phone,
        location=body.location,
        desired_role=body.desired_role,
        desired_salary_min=body.desired_salary_min,
        desired_salary_max=body.desired_salary_max,
        experience_years=body.experience_years,
        education_level=body.education_level,
        open_to_work=body.open_to_work,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    db: AsyncSession = Depends(get_db),
    status_filter: CandidateStatus | None = None,
):
    """List all candidates."""
    query = select(Candidate).order_by(Candidate.created_at.desc())
    if status_filter:
        query = query.where(Candidate.status == status_filter)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get candidate detail with CVs."""
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    cv_result = await db.execute(
        select(CandidateCV)
        .where(CandidateCV.candidate_id == candidate_id)
        .order_by(CandidateCV.created_at.desc())
    )
    cvs = cv_result.scalars().all()

    return CandidateDetailResponse(
        **{c.key: getattr(candidate, c.key) for c in Candidate.__table__.columns},
        cvs=[CVResponse.model_validate(cv) for cv in cvs],
    )


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: int,
    body: CandidateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update candidate profile."""
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)

    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a candidate and all associated CVs/chunks."""
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Clean up vector store chunks for all CVs
    cv_result = await db.execute(
        select(CandidateCV).where(CandidateCV.candidate_id == candidate_id)
    )
    for cv in cv_result.scalars().all():
        try:
            from app.services.job_processing_service import JobProcessingService
            svc = JobProcessingService(db)
            svc.delete_cv_chunks(cv.id)
        except Exception:
            pass
        if cv.filename:
            file_path = UPLOAD_DIR / cv.filename
            if file_path.exists():
                os.remove(file_path)

    await db.delete(candidate)
    await db.commit()


# ------------------------------------------------------------------
# CV Upload & Processing
# ------------------------------------------------------------------

@router.post("/{source_candidate_id}/upload-cv", response_model=CVUploadResponse)
async def upload_cv(
    source_candidate_id: int,
    source_cv_id: int = Form(..., alias="sourceCvId"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CV file for a candidate resolved by source ID."""
    reference_service = CandidateReferenceService(db)
    try:
        upload_context = await reference_service.prepare_candidate_cv_upload(
            source_candidate_id=source_candidate_id,
            source_cv_id=source_cv_id,
        )
    except SourceCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CandidateCVMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {ext} not allowed. Allowed: {ALLOWED_EXTENSIONS}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    candidate = upload_context.candidate
    cv = upload_context.cv
    old_filename = cv.filename
    old_status = cv.status

    filename = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(content)

    if not upload_context.created and (
        cv.chunk_count > 0 or old_status == CVStatus.INDEXED
    ):
        from app.services.job_processing_service import JobProcessingService

        JobProcessingService(db).delete_cv_chunks(cv.id)

    cv.source_cv_id = source_cv_id
    cv.candidate_id = candidate.id
    cv.filename = filename
    cv.original_filename = file.filename
    cv.file_type = ext[1:]
    cv.file_size = len(content)
    cv.is_searchable = False
    cv.status = CVStatus.PENDING
    cv.content_hash = None
    cv.markdown_content = None
    cv.chunk_count = 0
    cv.page_count = 0
    cv.skills_extracted = None
    cv.experience_extracted = None
    cv.education_extracted = None
    cv.summary_extracted = None
    cv.processing_time_ms = 0
    cv.error_message = None

    await db.commit()
    await db.refresh(cv)

    if old_filename and old_filename != filename:
        old_file_path = UPLOAD_DIR / old_filename
        if old_file_path.exists():
            os.remove(old_file_path)

    return CVUploadResponse(
        id=cv.id,
        source_candidate_id=(
            candidate.source_candidate_id
            if candidate.source_candidate_id is not None
            else source_candidate_id
        ),
        source_cv_id=cv.source_cv_id,
        candidate_id=candidate.id,
        filename=cv.original_filename,
        status=cv.status,
        message="CV uploaded. Trigger processing to extract and index.",
    )


@router.post("/{source_candidate_id}/process/{source_cv_id}", response_model=CVProcessResponse)
async def process_cv(
    source_candidate_id: int,
    source_cv_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger CV processing (parse + extract + index) by source IDs."""
    reference_service = CandidateReferenceService(db)
    try:
        candidate, cv = await reference_service.require_candidate_cv_pair(
            source_candidate_id=source_candidate_id,
            source_cv_id=source_cv_id,
        )
    except SourceCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SourceCVNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CandidateCVMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if cv.status == CVStatus.INDEXED:
        return CVProcessResponse(
            status="already_indexed",
            source_candidate_id=(
                candidate.source_candidate_id
                if candidate.source_candidate_id is not None
                else source_candidate_id
            ),
            source_cv_id=cv.source_cv_id if cv.source_cv_id is not None else source_cv_id,
            chunk_count=cv.chunk_count,
            message="CV already indexed",
        )

    if cv.status in (CVStatus.PARSING, CVStatus.INDEXING):
        raise HTTPException(status_code=400, detail="CV is already being processed")

    if not cv.filename:
        raise HTTPException(status_code=404, detail="CV file not found on disk")

    file_path = UPLOAD_DIR / cv.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="CV file not found on disk")

    # Background processing
    import asyncio
    from app.core.database import async_session_maker

    async def _process():
        async with async_session_maker() as session:
            from app.services.job_processing_service import JobProcessingService
            svc = JobProcessingService(session)
            await svc.process_cv(cv.id, str(file_path))

    asyncio.create_task(_process())

    return CVProcessResponse(
        status="processing",
        source_candidate_id=(
            candidate.source_candidate_id
            if candidate.source_candidate_id is not None
            else source_candidate_id
        ),
        source_cv_id=cv.source_cv_id if cv.source_cv_id is not None else source_cv_id,
        message="CV processing started",
    )


@router.get("/{source_candidate_id}/recommendations")
async def get_candidate_recommendations(
    source_candidate_id: int,
    top_k: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get job recommendations for a candidate (triggers fresh matching)."""
    from app.services.matching_service import MatchingService

    svc = MatchingService(db)
    try:
        candidate, matches = await svc.match_candidate_to_jobs_by_source_candidate_id(
            source_candidate_id,
            top_k=top_k,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "candidate_id": candidate.id,
        "source_candidate_id": candidate.source_candidate_id,
        "total": len(matches),
        "matches": [
            {
                "id": m.id,
                "mode": m.mode.value,
                "job_id": m.job_id,
                "candidate_cv_id": m.candidate_cv_id,
                "application_id": m.application_id,
                "overall_score": m.overall_score,
                "semantic_score": m.semantic_score,
                "skill_match_score": m.skill_match_score,
                "experience_score": m.experience_score,
                "location_score": m.location_score,
                "salary_score": m.salary_score,
                "matched_skills": m.matched_skills,
                "missing_skills": m.missing_skills,
                "explanation": m.explanation,
                "status": m.status.value,
            }
            for m in matches
        ],
    }
