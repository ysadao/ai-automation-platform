from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    email_verified_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    verification_token: str | None = None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    first_name: str = ""
    last_name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str | None = None


class VerifyEmailIn(BaseModel):
    token: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)


class SessionOut(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    ip: str | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    current: bool = False

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1)
    workflow_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    webhook_url: str | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    prompt: str
    workflow_id: uuid.UUID | None
    template_id: uuid.UUID | None
    status: str
    result: str | None
    error: str | None
    tokens_used: int
    webhook_url: str | None
    steps: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    steps: list[dict[str, Any]] = Field(min_length=1)


class WorkflowOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    steps: list[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageOut(BaseModel):
    total_tokens: int
    task_count: int
