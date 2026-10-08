from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CareTaskType = Literal["inspection", "followup", "handover"]
CareTaskPriority = Literal["P0", "P1", "P2"]
CareTaskStatus = Literal["pending", "done"]


class CareTaskRecord(BaseModel):
    """A single care task shown in the duty sidebar and follow-up list."""

    id: str
    community_id: str
    elder_id: str | None = None
    family_ids: list[str] = Field(default_factory=list)
    task_type: CareTaskType
    priority: CareTaskPriority
    title: str
    note: str = ""
    owner: str = ""
    due_at: str | None = None
    status: CareTaskStatus
    created_by: str = ""
    created_at: str
    done_at: str | None = None


class CareTaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    task_type: CareTaskType = "followup"
    priority: CareTaskPriority = "P2"
    elder_id: str | None = Field(default=None, max_length=80)
    note: str = Field(default="", max_length=500)
    owner: str = Field(default="", max_length=80)
    due_at: str | None = Field(default=None, max_length=40)


class CareTaskUpdateRequest(BaseModel):
    status: CareTaskStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    priority: CareTaskPriority | None = None
    note: str | None = Field(default=None, max_length=500)
    owner: str | None = Field(default=None, max_length=80)
    due_at: str | None = Field(default=None, max_length=40)


class CareTaskDeleteResponse(BaseModel):
    id: str
    deleted: bool
