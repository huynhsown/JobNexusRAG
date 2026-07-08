from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, CandidateCV
from app.models.job import Company, EmploymentType, JobPosting, JobStatus
from app.models.job_application import (
    ApplicationStatus,
    CvResolutionStatus,
    JobApplication,
)
from app.schemas.sync import (
    ApplicationSyncRequest,
    CandidateCvSyncRequest,
    CandidateSyncRequest,
    CompanySyncRequest,
    JobSyncRequest,
)


class SyncReferenceError(ValueError):
    """Raised when source-of-truth data references entities not yet present in AI DB."""


@dataclass
class SyncOutcome:
    entity: str
    instance_id: int
    source_id: int | None
    status: str
    message: str
    warnings: list[str] = field(default_factory=list)
    candidate_cv_id: int | None = None
    cv_resolution_status: CvResolutionStatus | None = None


class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_candidate(self, payload: CandidateSyncRequest) -> SyncOutcome:
        candidate = await self._find_candidate_by_source_id(payload.source_candidate_id)
        created = candidate is None
        if candidate is None:
            candidate = Candidate(
                source_candidate_id=payload.source_candidate_id,
                name=payload.name,
            )
            self.db.add(candidate)

        candidate.name = payload.name
        self._assign_if_present(candidate, "email", payload)
        self._assign_if_present(candidate, "phone", payload)
        self._assign_if_present(candidate, "location", payload)
        self._assign_if_present(candidate, "desired_role", payload)
        self._assign_if_present(candidate, "experience_years", payload)
        self._assign_if_present(candidate, "education_level", payload)
        self._assign_if_present(candidate, "desired_salary_min", payload)
        self._assign_if_present(candidate, "desired_salary_max", payload)
        self._assign_if_present(candidate, "open_to_work", payload)
        self._assign_if_present(candidate, "status", payload)

        await self.db.commit()
        await self.db.refresh(candidate)
        return SyncOutcome(
            entity="candidate",
            instance_id=candidate.id,
            source_id=candidate.source_candidate_id,
            status="created" if created else "updated",
            message="Candidate synced into AI DB",
        )

    async def upsert_candidate_cv(self, payload: CandidateCvSyncRequest) -> SyncOutcome:
        candidate = await self._require_candidate_by_source_id(payload.source_candidate_id)
        cv = await self._find_cv_by_source_id(payload.source_cv_id)
        created = cv is None
        if cv is None:
            cv = CandidateCV(
                source_cv_id=payload.source_cv_id,
                candidate_id=candidate.id,
            )
            self.db.add(cv)

        cv.candidate_id = candidate.id
        self._assign_if_present(cv, "title", payload)
        self._assign_if_present(cv, "filename", payload)
        self._assign_if_present(cv, "original_filename", payload)
        self._assign_if_present(cv, "file_size", payload)
        self._assign_if_present(cv, "file_type", payload)
        self._assign_if_present(cv, "content_hash", payload)
        self._assign_if_present(cv, "status", payload)
        self._assign_if_present(cv, "markdown_content", payload)
        self._assign_if_present(cv, "summary_extracted", payload)
        self._assign_if_present(cv, "experience_extracted", payload)
        self._assign_if_present(cv, "education_extracted", payload)
        self._assign_if_present(cv, "skills_extracted", payload)
        self._assign_if_present(cv, "chunk_count", payload)
        self._assign_if_present(cv, "page_count", payload)
        self._assign_if_present(cv, "processing_time_ms", payload)
        self._assign_if_present(cv, "error_message", payload)

        if "is_searchable" in payload.model_fields_set:
            if payload.is_searchable:
                await self.db.execute(
                    update(CandidateCV)
                    .where(
                        CandidateCV.candidate_id == candidate.id,
                        CandidateCV.id != cv.id,
                    )
                    .values(is_searchable=False)
                )
            cv.is_searchable = payload.is_searchable

        await self.db.commit()
        await self.db.refresh(cv)
        return SyncOutcome(
            entity="candidate_cv",
            instance_id=cv.id,
            source_id=cv.source_cv_id,
            status="created" if created else "updated",
            message="Candidate CV synced into AI DB",
        )

    async def upsert_company(self, payload: CompanySyncRequest) -> SyncOutcome:
        company = await self._find_company_by_source_id(payload.source_company_id)
        created = company is None
        if company is None:
            company = Company(
                source_company_id=payload.source_company_id,
                name=payload.name,
            )
            self.db.add(company)

        company.name = payload.name
        self._assign_if_present(company, "industry", payload)
        self._assign_if_present(company, "location", payload)
        self._assign_if_present(company, "size", payload)
        self._assign_if_present(company, "description", payload)

        await self.db.commit()
        await self.db.refresh(company)
        return SyncOutcome(
            entity="company",
            instance_id=company.id,
            source_id=company.source_company_id,
            status="created" if created else "updated",
            message="Company synced into AI DB",
        )

    async def upsert_job(self, payload: JobSyncRequest) -> SyncOutcome:
        company = await self._require_company_by_source_id(payload.source_company_id)
        job = await self._find_job_by_source_id(payload.source_job_id)
        created = job is None
        if job is None:
            job = JobPosting(
                source_job_id=payload.source_job_id,
                company_id=company.id,
                title=payload.title,
                employment_type=payload.employment_type or EmploymentType.FULL_TIME,
                status=payload.status or JobStatus.DRAFT,
            )
            self.db.add(job)

        job.company_id = company.id
        job.title = payload.title
        self._assign_if_present(job, "description_text", payload)
        self._assign_if_present(job, "markdown_content", payload)
        self._assign_if_present(job, "location", payload)
        self._assign_if_present(job, "employment_type", payload)
        self._assign_if_present(job, "experience_required", payload)
        self._assign_if_present(job, "salary_min", payload)
        self._assign_if_present(job, "salary_max", payload)
        self._assign_if_present(job, "skills_required", payload)
        self._assign_if_present(job, "skills_nice_to_have", payload)
        self._assign_if_present(job, "status", payload)

        await self.db.commit()
        await self.db.refresh(job)
        return SyncOutcome(
            entity="job_posting",
            instance_id=job.id,
            source_id=job.source_job_id,
            status="created" if created else "updated",
            message="Job synced into AI DB",
        )

    async def upsert_application(self, payload: ApplicationSyncRequest) -> SyncOutcome:
        candidate = await self._require_candidate_by_source_id(payload.source_candidate_id)
        job = await self._require_job_by_source_id(payload.source_job_id)

        application = await self._find_application_by_source_id(payload.source_application_id)
        if application is None:
            result = await self.db.execute(
                select(JobApplication).where(
                    JobApplication.job_id == job.id,
                    JobApplication.candidate_id == candidate.id,
                )
            )
            application = result.scalar_one_or_none()

        created = application is None
        warnings: list[str] = []

        if application is None:
            application = JobApplication(
                source_application_id=payload.source_application_id,
                job_id=job.id,
                candidate_id=candidate.id,
            )
            self.db.add(application)

        application.source_application_id = payload.source_application_id
        application.job_id = job.id
        application.candidate_id = candidate.id
        if "status" in payload.model_fields_set and payload.status is not None:
            application.status = payload.status
        elif created:
            application.status = ApplicationStatus.APPLIED
        self._assign_if_present(application, "note", payload)
        self._assign_if_present(application, "applied_at", payload)
        self._assign_if_present(application, "updated_at", payload)

        if payload.source_cv_id is not None:
            cv = await self._find_cv_by_source_id(payload.source_cv_id)
            if cv is None:
                raise SyncReferenceError(
                    "Application payload references sourceCvId that is not present in AI DB. "
                    "Sync CV first, then retry application sync."
                )
            if cv.candidate_id != candidate.id:
                raise SyncReferenceError(
                    "Application payload references a CV that does not belong to the candidate."
                )

            application.candidate_cv_id = cv.id
            application.cv_resolution_status = CvResolutionStatus.RESOLVED
        else:
            resolved_cv, resolution_status, resolution_warning = await self._resolve_cv_for_legacy_application(
                candidate_id=candidate.id
            )
            application.candidate_cv_id = resolved_cv.id if resolved_cv else None
            application.cv_resolution_status = resolution_status
            if resolution_warning:
                warnings.append(resolution_warning)

        if warnings:
            notes = [application.note] if application.note else []
            notes.extend(warnings)
            application.note = " | ".join(notes)

        await self.db.commit()
        await self.db.refresh(application)
        return SyncOutcome(
            entity="job_application",
            instance_id=application.id,
            source_id=application.source_application_id,
            status="created" if created else "updated",
            message="Application synced into AI DB",
            warnings=warnings,
            candidate_cv_id=application.candidate_cv_id,
            cv_resolution_status=application.cv_resolution_status,
        )

    async def resolve_local_application(
        self,
        *,
        job_id: int,
        candidate_id: int,
        candidate_cv_id: int | None,
        note: str | None,
    ) -> SyncOutcome:
        result = await self.db.execute(select(JobPosting).where(JobPosting.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise SyncReferenceError(f"JobPosting {job_id} not found")

        result = await self.db.execute(select(Candidate).where(Candidate.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise SyncReferenceError(f"Candidate {candidate_id} not found")

        result = await self.db.execute(
            select(JobApplication).where(
                JobApplication.job_id == job_id,
                JobApplication.candidate_id == candidate_id,
            )
        )
        application = result.scalar_one_or_none()
        created = application is None
        if application is None:
            application = JobApplication(job_id=job_id, candidate_id=candidate_id)
            self.db.add(application)

        warnings: list[str] = []
        application.status = ApplicationStatus.APPLIED
        application.note = note

        if candidate_cv_id is not None:
            result = await self.db.execute(
                select(CandidateCV).where(
                    CandidateCV.id == candidate_cv_id,
                    CandidateCV.candidate_id == candidate_id,
                )
            )
            cv = result.scalar_one_or_none()
            if cv is None:
                raise SyncReferenceError(
                    f"Candidate CV {candidate_cv_id} not found for candidate {candidate_id}"
                )
            application.candidate_cv_id = cv.id
            application.cv_resolution_status = CvResolutionStatus.RESOLVED
        else:
            resolved_cv, resolution_status, resolution_warning = await self._resolve_cv_for_legacy_application(
                candidate_id=candidate_id
            )
            application.candidate_cv_id = resolved_cv.id if resolved_cv else None
            application.cv_resolution_status = resolution_status
            if resolution_warning:
                warnings.append(resolution_warning)

        if warnings:
            notes = [application.note] if application.note else []
            notes.extend(warnings)
            application.note = " | ".join(notes)

        await self.db.commit()
        await self.db.refresh(application)
        return SyncOutcome(
            entity="job_application",
            instance_id=application.id,
            source_id=application.source_application_id,
            status="created" if created else "updated",
            message="Application stored in AI DB",
            warnings=warnings,
            candidate_cv_id=application.candidate_cv_id,
            cv_resolution_status=application.cv_resolution_status,
        )

    async def _resolve_cv_for_legacy_application(
        self,
        *,
        candidate_id: int,
    ) -> tuple[CandidateCV | None, CvResolutionStatus, str | None]:
        result = await self.db.execute(
            select(CandidateCV)
            .where(CandidateCV.candidate_id == candidate_id)
            .order_by(CandidateCV.updated_at.desc(), CandidateCV.created_at.desc())
        )
        cvs = result.scalars().all()

        if not cvs:
            return (
                None,
                CvResolutionStatus.MISSING_CV_DATA,
                "Legacy application payload has no sourceCvId and candidate has no CV in AI DB.",
            )

        if len(cvs) == 1:
            if cvs[0].is_searchable:
                return (
                    cvs[0],
                    CvResolutionStatus.SEARCHABLE_ONLY_FALLBACK,
                    "Legacy application payload resolved by searchable-CV fallback.",
                )
            return (
                cvs[0],
                CvResolutionStatus.SINGLE_CV_FALLBACK,
                "Legacy application payload resolved by single-CV fallback.",
            )

        return (
            None,
            CvResolutionStatus.PENDING_CV_RESOLUTION,
            "Legacy application payload has no sourceCvId and candidate has multiple CVs; "
            "application kept pending CV resolution.",
        )

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

    async def _find_company_by_source_id(self, source_company_id: int) -> Company | None:
        result = await self.db.execute(
            select(Company).where(Company.source_company_id == source_company_id)
        )
        return result.scalar_one_or_none()

    async def _find_job_by_source_id(self, source_job_id: int) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting).where(JobPosting.source_job_id == source_job_id)
        )
        return result.scalar_one_or_none()

    async def _find_application_by_source_id(
        self,
        source_application_id: int,
    ) -> JobApplication | None:
        result = await self.db.execute(
            select(JobApplication).where(
                JobApplication.source_application_id == source_application_id
            )
        )
        return result.scalar_one_or_none()

    async def _require_candidate_by_source_id(self, source_candidate_id: int) -> Candidate:
        candidate = await self._find_candidate_by_source_id(source_candidate_id)
        if candidate is None:
            raise SyncReferenceError(
                f"Candidate with sourceCandidateId={source_candidate_id} not found in AI DB"
            )
        return candidate

    async def _require_company_by_source_id(self, source_company_id: int) -> Company:
        company = await self._find_company_by_source_id(source_company_id)
        if company is None:
            raise SyncReferenceError(
                f"Company with sourceCompanyId={source_company_id} not found in AI DB"
            )
        return company

    async def _require_job_by_source_id(self, source_job_id: int) -> JobPosting:
        job = await self._find_job_by_source_id(source_job_id)
        if job is None:
            raise SyncReferenceError(
                f"JobPosting with sourceJobId={source_job_id} not found in AI DB"
            )
        return job

    @staticmethod
    def _assign_if_present(instance: object, field_name: str, payload: object) -> None:
        if field_name in getattr(payload, "model_fields_set", set()):
            setattr(instance, field_name, getattr(payload, field_name))
