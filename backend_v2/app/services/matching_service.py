"""
Matching Service
=================

Three explicit business modes:
  1. Candidate finds jobs via searchable CV, or latest CV as fallback.
  2. Recruiter finds talent via searchable CVs from the open-to-work pool only.
  3. Recruiter ranks applicants via the exact CV attached to each application.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.candidate import Candidate, CandidateCV, CVStatus
from app.models.job import JobPosting, JobStatus
from app.models.job_application import (
    ApplicationStatus,
    CvResolutionStatus,
    JobApplication,
)
from app.models.match import MatchMode, MatchResult, MatchStatus
from app.services.embedder import get_embedding_service
from app.services.reranker import get_reranker_service
from app.services.vector_job_collections import _get_cv_vector_store, _get_jd_vector_store

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    """Intermediate match result before DB persistence."""

    candidate_id: int
    job_id: int
    mode: MatchMode
    candidate_cv_id: int | None = None
    application_id: int | None = None
    semantic_score: float = 0.0
    skill_match_score: float = 0.0
    experience_score: float = 0.0
    location_score: float = 0.0
    salary_score: float = 0.0
    overall_score: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    explanation: str = ""


class MatchingService:
    """Business-aware matching engine that keeps track of the CV context used."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedder = get_embedding_service()
        self.reranker = get_reranker_service()
        self.cv_store = _get_cv_vector_store()
        self.jd_store = _get_jd_vector_store()

    async def match_candidate_to_jobs(
        self,
        candidate_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[MatchResult]:
        """Mode CANDIDATE_FIND_JOBS."""
        candidate = await self._load_candidate(candidate_id)
        cv = await self._resolve_candidate_find_jobs_cv(candidate_id)

        query_text = self._build_candidate_query(candidate, cv)
        if not query_text.strip():
            raise ValueError(
                f"Candidate {candidate_id} has no searchable/latest CV content to match"
            )

        candidate_skills = self._normalize_skills(cv.skills_extracted)

        prefetch_k = max(settings.NEXUSRAG_VECTOR_PREFETCH, top_k * 3)
        query_embedding = self.embedder.embed_query(query_text)
        raw_results = self.jd_store.query(
            query_embedding=query_embedding,
            n_results=prefetch_k,
        )

        if not raw_results.get("documents"):
            return []

        reranked_pairs = self._rerank_documents(
            query_text=query_text,
            documents=raw_results["documents"],
            top_k=top_k * 2,
        )

        matches: list[MatchCandidate] = []
        seen_jobs: set[int] = set()

        for idx, semantic in reranked_pairs:
            meta = raw_results["metadatas"][idx] if raw_results.get("metadatas") else {}
            job_id = meta.get("job_id", 0)
            if not job_id or job_id in seen_jobs:
                continue

            job = await self._load_job(job_id)
            if job is None or job.status != JobStatus.OPEN:
                continue

            seen_jobs.add(job_id)
            matches.append(
                self._compute_structured_scores(
                    candidate=candidate,
                    cv=cv,
                    job=job,
                    candidate_skills=candidate_skills,
                    semantic_raw=semantic,
                    mode=MatchMode.CANDIDATE_FIND_JOBS,
                    candidate_cv_id=cv.id,
                )
            )

            if len(matches) >= top_k:
                break

        return await self._persist_matches(matches, min_score=min_score)

    async def match_candidate_to_jobs_by_source_candidate_id(
        self,
        source_candidate_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> tuple[Candidate, list[MatchResult]]:
        """Resolve source candidate id, then run candidate-to-jobs matching."""
        candidate = await self._require_candidate_by_source_id(source_candidate_id)
        matches = await self.match_candidate_to_jobs(
            candidate.id,
            top_k=top_k,
            min_score=min_score,
        )
        return candidate, matches

    async def match_job_to_candidates(
        self,
        job_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[MatchResult]:
        """Backward-compatible alias for JOB_RANK_APPLICANTS."""
        return await self.rank_job_applicants(job_id, top_k=top_k, min_score=min_score)

    async def match_job_to_all_candidates(
        self,
        job_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[MatchResult]:
        """Backward-compatible alias for JOB_FIND_TALENT."""
        return await self.find_talent_for_job(job_id, top_k=top_k, min_score=min_score)

    async def find_talent_for_job(
        self,
        job_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[MatchResult]:
        """Mode JOB_FIND_TALENT."""
        job = await self._require_job(job_id)
        query_text = self._build_job_query(job)
        if not query_text.strip():
            return []

        prefetch_k = max(settings.NEXUSRAG_VECTOR_PREFETCH, top_k * 4)
        query_embedding = self.embedder.embed_query(query_text)
        raw_results = self.cv_store.query(
            query_embedding=query_embedding,
            n_results=prefetch_k,
        )

        if not raw_results.get("documents"):
            return []

        reranked_pairs = self._rerank_documents(
            query_text=query_text,
            documents=raw_results["documents"],
            top_k=top_k * 3,
        )

        matches: list[MatchCandidate] = []
        seen_cvs: set[int] = set()

        for idx, semantic in reranked_pairs:
            meta = raw_results["metadatas"][idx] if raw_results.get("metadatas") else {}
            cv_id = meta.get("cv_id")
            if not cv_id or cv_id in seen_cvs:
                continue

            loaded = await self._load_searchable_talent_cv(cv_id)
            if loaded is None:
                continue

            candidate, cv = loaded
            seen_cvs.add(cv_id)

            matches.append(
                self._compute_structured_scores(
                    candidate=candidate,
                    cv=cv,
                    job=job,
                    candidate_skills=self._normalize_skills(cv.skills_extracted),
                    semantic_raw=semantic,
                    mode=MatchMode.JOB_FIND_TALENT,
                    candidate_cv_id=cv.id,
                )
            )

            if len(matches) >= top_k:
                break

        return await self._persist_matches(matches, min_score=min_score)

    async def find_talent_for_job_by_source_job_id(
        self,
        source_job_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> tuple[JobPosting, list[MatchResult]]:
        """Resolve source job id, then run talent search."""
        job = await self._require_job_by_source_id(source_job_id)
        matches = await self.find_talent_for_job(
            job.id,
            top_k=top_k,
            min_score=min_score,
        )
        return job, matches

    async def rank_job_applicants(
        self,
        job_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[MatchResult]:
        """Mode JOB_RANK_APPLICANTS."""
        job = await self._require_job(job_id)
        job_query = self._build_job_query(job)
        if not job_query.strip():
            return []

        applications_result = await self.db.execute(
            select(JobApplication)
            .where(
                JobApplication.job_id == job_id,
                JobApplication.status == ApplicationStatus.APPLIED,
            )
            .order_by(JobApplication.applied_at.desc())
        )
        applications = applications_result.scalars().all()

        ranking_inputs: list[tuple[JobApplication, Candidate, CandidateCV, str]] = []
        for application in applications:
            if application.candidate_cv_id is None:
                logger.warning(
                    "Skipping application %s for job %s: unresolved candidate_cv_id "
                    "(cv_resolution_status=%s)",
                    application.id,
                    job_id,
                    application.cv_resolution_status,
                )
                continue

            loaded = await self._load_candidate_with_exact_cv(
                candidate_id=application.candidate_id,
                cv_id=application.candidate_cv_id,
            )
            if loaded is None:
                logger.warning(
                    "Skipping application %s for job %s: candidate_cv_id=%s missing",
                    application.id,
                    job_id,
                    application.candidate_cv_id,
                )
                continue

            candidate, cv = loaded
            cv_text = self._build_candidate_query(candidate, cv)
            if not cv_text.strip():
                logger.warning(
                    "Skipping application %s for job %s: CV %s has no matchable content",
                    application.id,
                    job_id,
                    cv.id,
                )
                continue

            ranking_inputs.append((application, candidate, cv, cv_text))

        if not ranking_inputs:
            return []

        reranked = self.reranker.rerank(
            query=job_query,
            documents=[item[3] for item in ranking_inputs],
            top_k=min(len(ranking_inputs), top_k * 3),
            min_score=settings.NEXUSRAG_MIN_RELEVANCE_SCORE,
        )

        if not reranked:
            reranked_pairs = [(idx, 0.3) for idx in range(min(len(ranking_inputs), top_k))]
        else:
            reranked_pairs = [(row.index, row.score) for row in reranked]

        matches: list[MatchCandidate] = []
        seen_applications: set[int] = set()

        for idx, semantic in reranked_pairs:
            application, candidate, cv, _ = ranking_inputs[idx]
            if application.id in seen_applications:
                continue

            seen_applications.add(application.id)
            matches.append(
                self._compute_structured_scores(
                    candidate=candidate,
                    cv=cv,
                    job=job,
                    candidate_skills=self._normalize_skills(cv.skills_extracted),
                    semantic_raw=semantic,
                    mode=MatchMode.JOB_RANK_APPLICANTS,
                    candidate_cv_id=cv.id,
                    application_id=application.id,
                )
            )

            if len(matches) >= top_k:
                break

        return await self._persist_matches(matches, min_score=min_score)

    async def rank_job_applicants_by_source_job_id(
        self,
        source_job_id: int,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> tuple[JobPosting, list[MatchResult]]:
        """Resolve source job id, then rank applicants for that job."""
        job = await self._require_job_by_source_id(source_job_id)
        matches = await self.rank_job_applicants(
            job.id,
            top_k=top_k,
            min_score=min_score,
        )
        return job, matches

    async def _persist_matches(
        self,
        matches: list[MatchCandidate],
        min_score: float,
    ) -> list[MatchResult]:
        matches.sort(key=lambda item: item.overall_score, reverse=True)
        if min_score > 0:
            matches = [item for item in matches if item.overall_score >= min_score]

        db_matches: list[MatchResult] = []
        for mc in matches:
            db_match = MatchResult(
                mode=mc.mode,
                candidate_id=mc.candidate_id,
                job_id=mc.job_id,
                candidate_cv_id=mc.candidate_cv_id,
                application_id=mc.application_id,
                overall_score=mc.overall_score,
                semantic_score=mc.semantic_score,
                skill_match_score=mc.skill_match_score,
                experience_score=mc.experience_score,
                location_score=mc.location_score,
                salary_score=mc.salary_score,
                matched_skills=mc.matched_skills,
                missing_skills=mc.missing_skills,
                explanation=mc.explanation,
                status=MatchStatus.PENDING,
            )
            self.db.add(db_match)
            db_matches.append(db_match)

        await self.db.commit()
        for match in db_matches:
            await self.db.refresh(match)
        return db_matches

    def _compute_structured_scores(
        self,
        candidate: Candidate,
        cv: CandidateCV,
        job: JobPosting,
        candidate_skills: set[str],
        semantic_raw: float,
        mode: MatchMode,
        candidate_cv_id: int | None,
        application_id: int | None = None,
    ) -> MatchCandidate:
        """Compute weighted match score with all sub-scores."""
        w = settings

        semantic = self._normalize_semantic_score(semantic_raw)

        required = self._normalize_skills(job.skills_required)
        matched = candidate_skills & required
        missing = required - candidate_skills
        skill_score = len(matched) / max(len(required), 1)

        exp_score = self._experience_score(
            candidate.experience_years, job.experience_required
        )
        loc_score = self._location_score(candidate.location, job.location)
        sal_score = self._salary_score(
            candidate.desired_salary_min,
            candidate.desired_salary_max,
            job.salary_min,
            job.salary_max,
        )

        overall = (
            w.MATCHING_SEMANTIC_WEIGHT * semantic
            + w.MATCHING_SKILL_WEIGHT * skill_score
            + w.MATCHING_EXPERIENCE_WEIGHT * exp_score
            + w.MATCHING_LOCATION_WEIGHT * loc_score
            + w.MATCHING_SALARY_WEIGHT * sal_score
        )

        explanation_parts = [
            f"mode={mode.value}",
            f"cv_id={candidate_cv_id or 'unknown'}",
        ]
        if application_id is not None:
            explanation_parts.append(f"application_id={application_id}")
        if matched:
            explanation_parts.append(f"Matched skills: {', '.join(sorted(matched))}")
        if missing:
            explanation_parts.append(f"Missing skills: {', '.join(sorted(missing))}")
        explanation_parts.append(
            f"Experience: {candidate.experience_years or '?'}y vs required {job.experience_required or '?'}y"
        )
        explanation_parts.append(
            f"Location: {candidate.location or '?'} vs {job.location or '?'}"
        )

        return MatchCandidate(
            candidate_id=candidate.id,
            job_id=job.id,
            mode=mode,
            candidate_cv_id=candidate_cv_id,
            application_id=application_id,
            semantic_score=round(semantic, 4),
            skill_match_score=round(skill_score, 4),
            experience_score=round(exp_score, 4),
            location_score=round(loc_score, 4),
            salary_score=round(sal_score, 4),
            overall_score=round(overall, 4),
            matched_skills=sorted(matched),
            missing_skills=sorted(missing),
            explanation=" | ".join(explanation_parts),
        )

    @staticmethod
    def _experience_score(
        candidate_years: float | None,
        required_years: float | None,
    ) -> float:
        if candidate_years is None or required_years is None:
            return 0.5
        if required_years <= 0:
            return 1.0
        if candidate_years >= required_years:
            return 1.0

        gap = required_years - candidate_years
        return max(0.0, 1.0 - (gap / max(required_years, 1.0)))

    @staticmethod
    def _location_score(
        candidate_loc: str | None,
        job_loc: str | None,
    ) -> float:
        if not candidate_loc or not job_loc:
            return 0.5
        c = candidate_loc.lower().strip()
        j = job_loc.lower().strip()
        if c == j:
            return 1.0
        if c in j or j in c:
            return 0.8
        if "remote" in j:
            return 0.7
        return 0.2

    @staticmethod
    def _salary_score(
        c_min: float | None,
        c_max: float | None,
        j_min: float | None,
        j_max: float | None,
    ) -> float:
        if c_min is None and c_max is None:
            return 0.5
        if j_min is None and j_max is None:
            return 0.5

        c_lo = c_min or 0
        c_hi = c_max or c_lo * 1.5
        j_lo = j_min or 0
        j_hi = j_max or j_lo * 1.5

        if c_hi < j_lo or j_hi < c_lo:
            return 0.0

        overlap = min(c_hi, j_hi) - max(c_lo, j_lo)
        total = max(c_hi, j_hi) - min(c_lo, j_lo)
        if total <= 0:
            return 0.5
        return min(1.0, overlap / total)

    @staticmethod
    def _build_candidate_query(candidate: Candidate, cv: CandidateCV) -> str:
        parts: list[str] = []
        if cv.summary_extracted:
            parts.append(cv.summary_extracted)
        if candidate.desired_role:
            parts.append(f"Looking for: {candidate.desired_role}")
        if cv.skills_extracted:
            parts.append(f"Skills: {', '.join(cv.skills_extracted[:20])}")
        if not parts and cv.markdown_content:
            parts.append(cv.markdown_content[:1500])
        return " ".join(parts)

    @staticmethod
    def _build_job_query(job: JobPosting) -> str:
        parts = [job.title]
        if job.skills_required:
            parts.append(f"Required: {', '.join(job.skills_required[:20])}")
        if job.description_text:
            parts.append(job.description_text[:500])
        elif job.markdown_content:
            parts.append(job.markdown_content[:500])
        return " ".join(parts)

    @staticmethod
    def _normalize_semantic_score(semantic_raw: float) -> float:
        if 0.0 <= semantic_raw <= 1.0:
            return round(semantic_raw, 4)
        return round(max(0.0, min(1.0, (semantic_raw + 1.0) / 2.0)), 4)

    @staticmethod
    def _normalize_skills(skills: list[str] | None) -> set[str]:
        return {
            skill.strip().lower()
            for skill in (skills or [])
            if isinstance(skill, str) and skill.strip()
        }

    def _rerank_documents(
        self,
        query_text: str,
        documents: list[str],
        top_k: int,
    ) -> list[tuple[int, float]]:
        reranked = self.reranker.rerank(
            query=query_text,
            documents=documents,
            top_k=top_k,
            min_score=settings.NEXUSRAG_MIN_RELEVANCE_SCORE,
        )
        if not reranked:
            return [(idx, 0.3) for idx in range(min(3, len(documents)))]
        return [(row.index, row.score) for row in reranked]

    async def _load_candidate(self, candidate_id: int) -> Candidate:
        result = await self.db.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise ValueError(f"Candidate {candidate_id} not found")
        return candidate

    async def _load_job(self, job_id: int) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting).where(JobPosting.id == job_id)
        )
        return result.scalar_one_or_none()

    async def _require_job(self, job_id: int) -> JobPosting:
        job = await self._load_job(job_id)
        if job is None:
            raise ValueError(f"JobPosting {job_id} not found")
        return job

    async def _require_candidate_by_source_id(self, source_candidate_id: int) -> Candidate:
        result = await self.db.execute(
            select(Candidate).where(Candidate.source_candidate_id == source_candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise ValueError(
                f"Candidate with source_candidate_id={source_candidate_id} not found"
            )
        return candidate

    async def _require_job_by_source_id(self, source_job_id: int) -> JobPosting:
        result = await self.db.execute(
            select(JobPosting).where(JobPosting.source_job_id == source_job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"JobPosting with source_job_id={source_job_id} not found")
        return job

    async def _resolve_candidate_find_jobs_cv(self, candidate_id: int) -> CandidateCV:
        searchable_result = await self.db.execute(
            select(CandidateCV)
            .where(
                CandidateCV.candidate_id == candidate_id,
                CandidateCV.is_searchable.is_(True),
            )
            .order_by(CandidateCV.updated_at.desc(), CandidateCV.created_at.desc())
            .limit(1)
        )
        searchable_cv = searchable_result.scalar_one_or_none()
        if searchable_cv is not None:
            if self._cv_has_matchable_content(searchable_cv):
                return searchable_cv
            raise ValueError(
                f"Candidate {candidate_id} has a searchable CV but it is not ready for matching"
            )

        latest_result = await self.db.execute(
            select(CandidateCV)
            .where(CandidateCV.candidate_id == candidate_id)
            .order_by(CandidateCV.updated_at.desc(), CandidateCV.created_at.desc())
            .limit(1)
        )
        latest_cv = latest_result.scalar_one_or_none()
        if latest_cv is None:
            raise ValueError(f"Candidate {candidate_id} has no CVs")
        if not self._cv_has_matchable_content(latest_cv):
            raise ValueError(
                f"Candidate {candidate_id} latest CV is not ready for matching"
            )
        return latest_cv

    async def _load_searchable_talent_cv(
        self,
        cv_id: int,
    ) -> tuple[Candidate, CandidateCV] | None:
        result = await self.db.execute(
            select(CandidateCV).where(CandidateCV.id == cv_id)
        )
        cv = result.scalar_one_or_none()
        if cv is None:
            return None
        if not cv.is_searchable or cv.status != CVStatus.INDEXED:
            return None

        candidate = await self._load_candidate(cv.candidate_id)
        if candidate.open_to_work is not True:
            return None
        return candidate, cv

    async def _load_candidate_with_exact_cv(
        self,
        candidate_id: int,
        cv_id: int,
    ) -> tuple[Candidate, CandidateCV] | None:
        candidate = await self._load_candidate(candidate_id)
        result = await self.db.execute(
            select(CandidateCV).where(
                CandidateCV.id == cv_id,
                CandidateCV.candidate_id == candidate_id,
            )
        )
        cv = result.scalar_one_or_none()
        if cv is None:
            return None
        return candidate, cv

    @staticmethod
    def _cv_has_matchable_content(cv: CandidateCV) -> bool:
        return bool(
            cv.summary_extracted
            or cv.skills_extracted
            or cv.markdown_content
            or cv.status == CVStatus.INDEXED
        )

    async def list_rankable_applications(
        self,
        job_id: int,
    ) -> list[JobApplication]:
        result = await self.db.execute(
            select(JobApplication)
            .where(
                JobApplication.job_id == job_id,
                JobApplication.status == ApplicationStatus.APPLIED,
                JobApplication.candidate_cv_id.is_not(None),
                JobApplication.cv_resolution_status.in_(
                    [
                        CvResolutionStatus.RESOLVED,
                        CvResolutionStatus.SINGLE_CV_FALLBACK,
                        CvResolutionStatus.SEARCHABLE_ONLY_FALLBACK,
                    ]
                ),
            )
            .order_by(JobApplication.applied_at.desc())
        )
        return result.scalars().all()
