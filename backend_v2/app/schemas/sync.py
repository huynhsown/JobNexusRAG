"""
Schemas for syncing source-of-truth data from the main system into backend_v2.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.candidate import CVStatus, CandidateStatus
from app.models.job import EmploymentType, JobStatus
from app.models.job_application import ApplicationStatus, CvResolutionStatus


class SyncBaseModel(BaseModel):
    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class CandidateSyncRequest(SyncBaseModel):
    source_candidate_id: int = Field(alias="sourceCandidateId")
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    desired_role: str | None = Field(default=None, alias="desiredRole")
    experience_years: float | None = Field(default=None, alias="experienceYears")
    education_level: str | None = Field(default=None, alias="educationLevel")
    desired_salary_min: float | None = Field(default=None, alias="desiredSalaryMin")
    desired_salary_max: float | None = Field(default=None, alias="desiredSalaryMax")
    open_to_work: bool | None = Field(default=None, alias="openToWork")
    status: CandidateStatus | None = None


class CandidateCvSyncRequest(SyncBaseModel):
    source_cv_id: int = Field(alias="sourceCvId")
    source_candidate_id: int = Field(alias="sourceCandidateId")
    title: str | None = None
    filename: str | None = None
    original_filename: str | None = Field(default=None, alias="originalFilename")
    file_size: int | None = Field(default=None, alias="fileSize")
    file_type: str | None = Field(default=None, alias="fileType")
    content_hash: str | None = Field(default=None, alias="contentHash")
    is_searchable: bool | None = Field(default=None, alias="isSearchable")
    status: CVStatus | None = None
    markdown_content: str | None = Field(default=None, alias="markdownContent")
    summary_extracted: str | None = Field(default=None, alias="summaryExtracted")
    experience_extracted: list | None = Field(default=None, alias="experienceExtracted")
    education_extracted: list | None = Field(default=None, alias="educationExtracted")
    skills_extracted: list | None = Field(default=None, alias="skillsExtracted")
    chunk_count: int | None = Field(default=None, alias="chunkCount")
    page_count: int | None = Field(default=None, alias="pageCount")
    processing_time_ms: int | None = Field(default=None, alias="processingTimeMs")
    error_message: str | None = Field(default=None, alias="errorMessage")


class CompanySyncRequest(SyncBaseModel):
    source_company_id: int = Field(alias="sourceCompanyId")
    name: str
    industry: str | None = None
    location: str | None = None
    size: str | None = None
    description: str | None = None


class JobSyncRequest(SyncBaseModel):
    source_job_id: int = Field(alias="sourceJobId")
    source_company_id: int = Field(alias="sourceCompanyId")
    title: str
    description_text: str | None = Field(default=None, alias="descriptionText")
    markdown_content: str | None = Field(default=None, alias="markdownContent")
    location: str | None = None
    employment_type: EmploymentType | None = Field(default=None, alias="employmentType")
    experience_required: float | None = Field(default=None, alias="experienceRequired")
    salary_min: float | None = Field(default=None, alias="salaryMin")
    salary_max: float | None = Field(default=None, alias="salaryMax")
    skills_required: list[str] | None = Field(default=None, alias="skillsRequired")
    skills_nice_to_have: list[str] | None = Field(default=None, alias="skillsNiceToHave")
    status: JobStatus | None = None


class ApplicationSyncRequest(SyncBaseModel):
    source_application_id: int = Field(alias="sourceApplicationId")
    source_candidate_id: int = Field(alias="sourceCandidateId")
    source_job_id: int = Field(alias="sourceJobId")
    source_cv_id: int | None = Field(default=None, alias="sourceCvId")
    status: ApplicationStatus | None = None
    note: str | None = None
    applied_at: datetime | None = Field(default=None, alias="appliedAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class SyncResultResponse(SyncBaseModel):
    entity: str
    id: int
    source_id: int | None = Field(default=None, alias="sourceId")
    status: str
    message: str
    warnings: list[str] = Field(default_factory=list)
    candidate_cv_id: int | None = Field(default=None, alias="candidateCvId")
    cv_resolution_status: CvResolutionStatus | None = Field(
        default=None,
        alias="cvResolutionStatus",
    )


class CVExistsData(SyncBaseModel):
    exists: bool


class CVExistsResponse(SyncBaseModel):
    success: bool
    data: CVExistsData | None = None
    message: str | None = None
