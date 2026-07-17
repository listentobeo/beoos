from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.reports import (
    DailyReportPreview,
    DailyReportSendResult,
    DailyReportSettings,
    DailyReportSettingsUpdate,
)
from app.infrastructure.database import get_session
from app.services.daily_reports import DailyReportService

router = APIRouter(prefix="/businesses/{business_id}/reports", tags=["reports"])


@router.get("/daily/settings", response_model=DailyReportSettings)
async def daily_report_settings(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DailyReportSettings:
    try:
        return await DailyReportService(settings).settings_for_business(session, business_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/daily/settings", response_model=DailyReportSettings)
async def update_daily_report_settings(
    business_id: UUID,
    payload: DailyReportSettingsUpdate,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DailyReportSettings:
    try:
        return await DailyReportService(settings).update_settings(session, business_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/daily/preview", response_model=DailyReportPreview)
async def daily_report_preview(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DailyReportPreview:
    try:
        return await DailyReportService(settings).preview(session, business_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/daily/send-test", response_model=DailyReportSendResult)
async def send_daily_report_test(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DailyReportSendResult:
    try:
        return await DailyReportService(settings).send(session, business_id, mark_sent=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
