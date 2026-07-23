from fastapi import APIRouter

from app.db import DbSession
from app.schemas import SettingsOut, SettingsPatch
from app.services.progress import get_settings_row

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings(session: DbSession) -> SettingsOut:
    row = get_settings_row(session)
    session.commit()
    return SettingsOut.model_validate(row)


@router.patch("/settings")
def patch_settings(payload: SettingsPatch, session: DbSession) -> SettingsOut:
    row = get_settings_row(session)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, name, value)
    session.commit()
    return SettingsOut.model_validate(row)
