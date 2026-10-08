from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.dependencies import (
    get_care_service,
    get_care_task_repo,
    require_session_user,
)
from backend.models.auth_model import SessionUser
from backend.models.care_task_model import (
    CareTaskCreateRequest,
    CareTaskDeleteResponse,
    CareTaskRecord,
    CareTaskUpdateRequest,
)
from backend.models.user_model import UserRole


router = APIRouter(prefix="/care-tasks", tags=["care-tasks"])

_WORKSPACE_ROLES = {UserRole.COMMUNITY, UserRole.ADMIN}


def _require_user(authorization: str | None) -> SessionUser:
    try:
        return require_session_user(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _visible_elder_ids(user: SessionUser) -> list[str] | None:
    """None means unrestricted (community/admin). A list restricts to those elders."""
    if user.role in _WORKSPACE_ROLES:
        return None
    if user.role == UserRole.FAMILY:
        care_service = get_care_service()
        elder_ids = care_service.resolve_family_elder_ids(user.id)
        if elder_ids:
            return list(elder_ids)
        demo_directory = care_service.get_demo_directory()
        family_key = user.family_id or user.id
        demo_family = next((item for item in demo_directory.families if item.id == family_key), None)
        return list(demo_family.elder_ids) if demo_family else []
    if user.role == UserRole.ELDER:
        return [user.id]
    return []


def _community_id(user: SessionUser) -> str:
    return (user.community_id or "").strip() or "default"


@router.get("", response_model=list[CareTaskRecord])
async def list_care_tasks(
    status: str | None = None,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> list[CareTaskRecord]:
    user = _require_user(authorization)
    tasks = get_care_task_repo().list_tasks(
        community_id=_community_id(user),
        elder_ids=_visible_elder_ids(user),
        status=status,
        limit=max(1, min(limit, 200)),
    )
    return [CareTaskRecord(**task) for task in tasks]


@router.post("", response_model=CareTaskRecord, status_code=201)
async def create_care_task(
    payload: CareTaskCreateRequest,
    authorization: str | None = Header(default=None),
) -> CareTaskRecord:
    user = _require_user(authorization)
    if user.role not in _WORKSPACE_ROLES:
        raise HTTPException(status_code=403, detail="ONLY_COMMUNITY_CAN_CREATE_TASK")

    family_ids: list[str] = []
    if payload.elder_id:
        directory = get_care_service().get_directory()
        elder = next((item for item in directory.elders if item.id == payload.elder_id), None)
        if elder is None:
            raise HTTPException(status_code=404, detail="ELDER_NOT_FOUND")
        family_ids = list(elder.family_ids or [])

    task = get_care_task_repo().create_task(
        community_id=_community_id(user),
        title=payload.title.strip(),
        task_type=payload.task_type,
        priority=payload.priority,
        elder_id=payload.elder_id,
        family_ids=family_ids,
        note=payload.note.strip(),
        owner=payload.owner.strip() or user.name,
        due_at=payload.due_at,
        created_by=user.id,
    )
    return CareTaskRecord(**task)


@router.patch("/{task_id}", response_model=CareTaskRecord)
async def update_care_task(
    task_id: str,
    payload: CareTaskUpdateRequest,
    authorization: str | None = Header(default=None),
) -> CareTaskRecord:
    user = _require_user(authorization)
    repo = get_care_task_repo()

    existing = repo.get_task(task_id)
    if existing is None or existing["community_id"] != _community_id(user):
        raise HTTPException(status_code=404, detail="CARE_TASK_NOT_FOUND")

    visible = _visible_elder_ids(user)
    if visible is not None and existing["elder_id"] not in visible:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    # 家属只能勾选完成/取消完成，不能改任务内容
    if user.role not in _WORKSPACE_ROLES and any(
        value is not None
        for value in (payload.title, payload.priority, payload.note, payload.owner, payload.due_at)
    ):
        raise HTTPException(status_code=403, detail="ONLY_STATUS_UPDATE_ALLOWED")

    updated = repo.update_task(
        task_id,
        status=payload.status,
        title=payload.title,
        priority=payload.priority,
        note=payload.note,
        owner=payload.owner,
        due_at=payload.due_at,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="CARE_TASK_NOT_FOUND")
    return CareTaskRecord(**updated)


@router.delete("/{task_id}", response_model=CareTaskDeleteResponse)
async def delete_care_task(
    task_id: str,
    authorization: str | None = Header(default=None),
) -> CareTaskDeleteResponse:
    user = _require_user(authorization)
    if user.role not in _WORKSPACE_ROLES:
        raise HTTPException(status_code=403, detail="ONLY_COMMUNITY_CAN_DELETE_TASK")

    repo = get_care_task_repo()
    existing = repo.get_task(task_id)
    if existing is None or existing["community_id"] != _community_id(user):
        raise HTTPException(status_code=404, detail="CARE_TASK_NOT_FOUND")

    return CareTaskDeleteResponse(id=task_id, deleted=repo.delete_task(task_id))
