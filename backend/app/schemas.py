from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


RoleValue = Literal["teacher", "student"]
StatusValue = Literal["present", "absent", "late"]


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: RoleValue
    student_id: str | None = Field(default=None, max_length=50)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: RoleValue
    student_id: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class SubjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)


class SubjectResponse(SubjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ClassCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    section: str = Field(default="A", min_length=1, max_length=40)
    subject_id: int


class ClassResponse(BaseModel):
    id: int
    name: str
    section: str
    subject_id: int
    subject_code: str
    subject_name: str
    enrolled_count: int
    active_session_id: int | None = None


class EnrollRequest(BaseModel):
    email: EmailStr


class StudentBrief(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    student_id: str | None = None


class SessionResponse(BaseModel):
    id: int
    class_id: int
    class_name: str
    subject_name: str
    token: str
    qr_payload: str
    starts_at: datetime
    expires_at: datetime
    closed_at: datetime | None = None
    marked_count: int


class ScanRequest(BaseModel):
    session_id: int
    token: str = Field(min_length=8, max_length=128)


class ManualAttendanceRequest(BaseModel):
    student_id: int
    status: StatusValue
    note: str | None = Field(default=None, max_length=255)


class AttendanceRecordResponse(BaseModel):
    id: int
    session_id: int
    class_id: int
    class_name: str
    subject_name: str
    student_id: int
    student_name: str
    student_email: EmailStr
    status: StatusValue
    source: str
    marked_at: datetime
    note: str | None = None


class AttendanceSummary(BaseModel):
    class_id: int
    class_name: str
    subject_name: str
    total_sessions: int
    present_count: int
    late_count: int
    absent_count: int
    percentage: float
    below_threshold: bool


class AuditResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str | None
    details: str | None
    created_at: datetime
    actor_name: str | None
