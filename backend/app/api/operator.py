from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_business_access
from app.domain.operator import OperatorChatRequest, OperatorChatResponse
from app.infrastructure.database import get_session
from app.services.operator import OperatorService

router = APIRouter(prefix="/businesses/{business_id}/operator", tags=["operator"])


@router.post("/chat", response_model=OperatorChatResponse)
async def operator_chat(
    business_id: UUID,
    payload: OperatorChatRequest,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> OperatorChatResponse:
    service = OperatorService(settings)
    return await service.chat(
        session=session,
        business_id=business_id,
        user_id=access.user_id,
        message=payload.message,
        mode=payload.mode,
        conversation_context=payload.conversation_context,
    )
