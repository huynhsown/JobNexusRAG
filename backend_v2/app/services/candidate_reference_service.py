"""
Helpers for resolving source IDs from the main DB into AI DB records.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, CandidateCV


class SourceCandidateNotFoundError(ValueError):
    """Raised when a source_candidate_id cannot be resolved in the AI DB."""


class SourceCVNotFoundError(ValueError):
    """Raised when a source_cv_id cannot be resolved in the AI DB."""


class CandidateCVMismatchError(ValueError):
    """Raised when a CV does not belong to the candidate resolved from source IDs."""


@dataclass(slots=True)
class CandidateCVUploadContext:
    candidate: Candidate
    cv: CandidateCV
    created: bool


class CandidateReferenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def require_candidate_by_source_id(self, source_candidate_id: int) -> Candidate:
        candidate = await self._find_candidate_by_source_id(source_candidate_id)
        if candidate is None:
            raise SourceCandidateNotFoundError(
                f"Candidate with source_candidate_id={source_candidate_id} not found in AI DB"
            )
        return candidate

    async def require_cv_by_source_id(self, source_cv_id: int) -> CandidateCV:
        cv = await self._find_cv_by_source_id(source_cv_id)
        if cv is None:
            raise SourceCVNotFoundError(
                f"CandidateCV with source_cv_id={source_cv_id} not found in AI DB"
            )
        return cv

    async def require_candidate_cv_pair(
        self,
        *,
        source_candidate_id: int,
        source_cv_id: int,
    ) -> tuple[Candidate, CandidateCV]:
        candidate = await self.require_candidate_by_source_id(source_candidate_id)
        cv = await self.require_cv_by_source_id(source_cv_id)
        self._ensure_cv_belongs_to_candidate(
            candidate=candidate,
            cv=cv,
            source_candidate_id=source_candidate_id,
            source_cv_id=source_cv_id,
        )
        return candidate, cv

    async def prepare_candidate_cv_upload(
        self,
        *,
        source_candidate_id: int,
        source_cv_id: int,
    ) -> CandidateCVUploadContext:
        candidate = await self.require_candidate_by_source_id(source_candidate_id)

        cv = await self._find_cv_by_source_id(source_cv_id)
        if cv is None:
            cv = CandidateCV(
                source_cv_id=source_cv_id,
                candidate_id=candidate.id,
            )
            self.db.add(cv)
            return CandidateCVUploadContext(candidate=candidate, cv=cv, created=True)

        self._ensure_cv_belongs_to_candidate(
            candidate=candidate,
            cv=cv,
            source_candidate_id=source_candidate_id,
            source_cv_id=source_cv_id,
        )
        return CandidateCVUploadContext(candidate=candidate, cv=cv, created=False)

    async def _find_candidate_by_source_id(self, source_candidate_id: int) -> Candidate | None:
        result = await self.db.execute(
            select(Candidate).where(Candidate.source_candidate_id == source_candidate_id)
        )
        return result.scalar_one_or_none()

    async def _find_cv_by_source_id(self, source_cv_id: int) -> CandidateCV | None:
        result = await self.db.execute(
            select(CandidateCV).where(CandidateCV.source_cv_id == source_cv_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _ensure_cv_belongs_to_candidate(
        *,
        candidate: Candidate,
        cv: CandidateCV,
        source_candidate_id: int,
        source_cv_id: int,
    ) -> None:
        if cv.candidate_id != candidate.id:
            raise CandidateCVMismatchError(
                "CandidateCV with source_cv_id="
                f"{source_cv_id} does not belong to candidate with source_candidate_id="
                f"{source_candidate_id}"
            )
