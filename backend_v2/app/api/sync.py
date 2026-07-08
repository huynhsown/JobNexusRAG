"""
Sync endpoints for upserting source-of-truth entities from the main system.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.sync import (
    ApplicationSyncRequest,
    CVExistsResponse,
    CandidateCvSyncRequest,
    CandidateSyncRequest,
    CompanySyncRequest,
    JobSyncRequest,
    SyncResultResponse,
)
from app.services.candidate_reference_service import (
    CandidateReferenceService,
    SourceCVNotFoundError,
)
from app.services.sync_service import SyncOutcome, SyncReferenceError, SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/candidates", response_model=SyncResultResponse, status_code=status.HTTP_200_OK)
async def sync_candidate(
    body: CandidateSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SyncService(db)
    outcome = await service.upsert_candidate(body)
    return _to_response(outcome)


@router.post("/candidate-cvs", response_model=SyncResultResponse, status_code=status.HTTP_200_OK)
async def sync_candidate_cv(
    body: CandidateCvSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SyncService(db)
    try:
        outcome = await service.upsert_candidate_cv(body)
    except SyncReferenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_response(outcome)


@router.post("/companies", response_model=SyncResultResponse, status_code=status.HTTP_200_OK)
async def sync_company(
    body: CompanySyncRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SyncService(db)
    outcome = await service.upsert_company(body)
    return _to_response(outcome)


@router.post("/jobs", response_model=SyncResultResponse, status_code=status.HTTP_200_OK)
async def sync_job(
    body: JobSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SyncService(db)
    try:
        outcome = await service.upsert_job(body)
    except SyncReferenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_response(outcome)


@router.post("/applications", response_model=SyncResultResponse, status_code=status.HTTP_200_OK)
async def sync_application(
    body: ApplicationSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SyncService(db)
    try:
        outcome = await service.upsert_application(body)
    except SyncReferenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_response(outcome)


def _to_response(outcome: SyncOutcome) -> SyncResultResponse:
    return SyncResultResponse(
        entity=outcome.entity,
        id=outcome.instance_id,
        sourceId=outcome.source_id,
        status=outcome.status,
        message=outcome.message,
        warnings=outcome.warnings,
        candidateCvId=outcome.candidate_cv_id,
        cvResolutionStatus=outcome.cv_resolution_status,
    )


@router.get("/candidate-cvs/exists", response_model=CVExistsResponse, status_code=status.HTTP_200_OK)
async def check_candidate_cv_exists(
    source_cv_id: int = Query(..., description="Source CV ID to check"),
    db: AsyncSession = Depends(get_db),
):
    service = CandidateReferenceService(db)

    try:
        await service.require_cv_by_source_id(source_cv_id)
    except SourceCVNotFoundError:
        return JSONResponse(content={"success": True, "data": {"exists": False}})
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "message": "Internal server error",
            },
        )

    return JSONResponse(content={"success": True, "data": {"exists": True}})
