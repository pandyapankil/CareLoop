"""CareLoop — Pydantic models for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    date_of_birth: Optional[str] = None
    condition: str = Field(..., min_length=1)
    notes: Optional[str] = None


class EncounterCreate(BaseModel):
    author_role: str = Field(..., pattern="^(provider|patient)$")
    author_name: str = Field(..., min_length=1)
    type: str = Field(..., pattern="^(provider_update|patient_checkin)$")
    content: str = Field(..., min_length=1)


class QuestionCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class RiskFlag(BaseModel):
    flag: str
    severity: str = "medium"  # low, medium, high
    detail: str = ""


class TaskItem(BaseModel):
    title: str
    owner: str = "provider"  # provider or patient
    due_window: str = ""
    description: str = ""


class AnalysisResult(BaseModel):
    shared_summary: str = ""
    patient_summary: str = ""
    tasks: list[TaskItem] = []
    risk_flags: list[RiskFlag] = []


class TrendResult(BaseModel):
    trend_summary: str = ""
    patterns: list[str] = []
    direction: str = "stable"  # improving, stable, concerning
