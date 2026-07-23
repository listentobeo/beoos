from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.tools import (
    ToolCallView,
    ToolExecuteRequest,
    ToolPermissionUpdate,
    ToolView,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    Role,
    ToolDefinition,
    ToolPermission,
    WorkflowDefinition,
)
from app.services.tool_registry import ToolRegistry, tool_spec

router = APIRouter(prefix="/businesses/{business_id}/tools", tags=["tools"])


@router.get("", response_model=list[ToolView])
async def list_tools(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[ToolView]:
    registry = ToolRegistry()
    definitions = await registry.sync_definitions(session)
    permissions = (
        await session.scalars(
            select(ToolPermission).where(ToolPermission.business_id == business_id)
        )
    ).all()
    await session.commit()
    by_tool: dict[UUID, list[dict[str, object]]] = {}
    for permission in permissions:
        by_tool.setdefault(permission.tool_definition_id, []).append(
            {
                "id": str(permission.id),
                "workflow_definition_id": str(permission.workflow_definition_id)
                if permission.workflow_definition_id
                else None,
                "role": permission.role,
                "permission": permission.permission,
                "constraints": permission.constraints,
            }
        )
    return [_view(item, by_tool.get(item.id, [])) for item in definitions]


@router.put("/permissions", response_model=ToolView)
async def set_tool_permission(
    business_id: UUID,
    payload: ToolPermissionUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ToolView:
    registry = ToolRegistry()
    await registry.sync_definitions(session)
    definition = await session.scalar(
        select(ToolDefinition).where(ToolDefinition.key == payload.tool_key)
    )
    if definition is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if payload.workflow_definition_id:
        workflow = await session.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == payload.workflow_definition_id,
                WorkflowDefinition.business_id == business_id,
            )
        )
        if workflow is None:
            raise HTTPException(status_code=404, detail="Tenant workflow not found")
    permission = await session.scalar(
        select(ToolPermission).where(
            ToolPermission.business_id == business_id,
            ToolPermission.tool_definition_id == definition.id,
            ToolPermission.workflow_definition_id == payload.workflow_definition_id,
            ToolPermission.role == payload.role,
        )
    )
    if permission is None:
        permission = ToolPermission(
            business_id=business_id,
            tool_definition_id=definition.id,
            workflow_definition_id=payload.workflow_definition_id,
            role=payload.role,
            approved_by=access.user_id,
        )
        session.add(permission)
    permission.permission = payload.permission
    permission.constraints = payload.constraints
    permission.approved_by = access.user_id
    await session.commit()
    return _view(
        definition,
        [
            {
                "id": str(permission.id),
                "workflow_definition_id": str(permission.workflow_definition_id)
                if permission.workflow_definition_id
                else None,
                "role": permission.role,
                "permission": permission.permission,
                "constraints": permission.constraints,
            }
        ],
    )


@router.post("/execute", response_model=ToolCallView)
async def execute_tool(
    business_id: UUID,
    payload: ToolExecuteRequest,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> ToolCallView:
    try:
        call = await ToolRegistry().execute(
            session,
            business_id=business_id,
            workflow_run_id=payload.workflow_run_id,
            workflow_step_id=payload.workflow_step_id,
            tool_key=payload.tool_key,
            payload=payload.payload,
            role=Role(access.role),
            user_id=access.user_id,
            idempotency_key=payload.idempotency_key,
            requested_permission=payload.permission,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    definition = await session.get(ToolDefinition, call.tool_definition_id)
    return ToolCallView(
        id=call.id,
        status=call.status,
        tool_key=definition.key if definition else payload.tool_key,
        response=call.response_payload_sanitized,
        error_code=call.error_code,
        error_message=call.error_message_sanitized,
    )


def _view(definition: ToolDefinition, permissions: list[dict[str, object]]) -> ToolView:
    spec = tool_spec(definition.key)
    return ToolView(
        id=definition.id,
        key=definition.key,
        name=definition.name,
        description=definition.description,
        risk_level=definition.risk_level,
        is_external=definition.is_external,
        is_reversible=definition.is_reversible,
        requires_approval_by_default=definition.requires_approval_by_default,
        enabled=definition.enabled,
        input_schema=definition.input_schema,
        output_schema=definition.output_schema,
        required_role=spec.required_role.value,
        idempotency_strategy=spec.idempotency_strategy,
        timeout_seconds=spec.timeout_seconds,
        retry_policy=spec.retry_policy,
        failure_mapping=spec.failure_mapping,
        permissions=permissions,
    )
