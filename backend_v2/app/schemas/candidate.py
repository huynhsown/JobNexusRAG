"""
Candidate & CV schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.candidate import CandidateStatus, CVStatus


class CandidateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    desired_role: str | None = None
    desired_salary_min: float | None = None
    desired_salary_max: float | None = None
    experience_years: float | None = None
    education_level: str | None = None
    open_to_work: bool | None = None


class CandidateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    desired_role: str | None = None
    desired_salary_min: float | None = None
    desired_salary_max: float | None = None
    experience_years: float | None = None
    education_level: str | None = None
    open_to_work: bool | None = None
    status: CandidateStatus | None = None


class CandidateResponse(BaseModel):
    id: int
    source_candidate_id: int | None = None
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    desired_role: str | None = None
    desired_salary_min: float | None = None
    desired_salary_max: float | None = None
    experience_years: float | None = None
    education_level: str | None = None
    open_to_work: bool | None = None
    status: CandidateStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CVUploadResponse(BaseModel):
    id: int
    source_candidate_id: int
    source_cv_id: int
    candidate_id: int
    filename: str
    status: CVStatus
    message: str


class CVProcessResponse(BaseModel):
    status: str
    source_candidate_id: int
    source_cv_id: int
    chunk_count: int | None = None
    message: str


class CVResponse(BaseModel):
    id: int
    source_cv_id: int | None = None
    candidate_id: int
    title: str | None = None
    filename: str | None = None
    original_filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    is_searchable: bool = False
    content_hash: str | None = None
    status: CVStatus
    chunk_count: int = 0
    page_count: int = 0
    skills_extracted: list | None = None
    experience_extracted: list | None = None
    education_extracted: list | None = None
    summary_extracted: str | None = None
    processing_time_ms: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateDetailResponse(CandidateResponse):
    cvs: list[CVResponse] = []
