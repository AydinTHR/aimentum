from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import DbSession
from app.models import Retro
from app.schemas import RetroOut

router = APIRouter(tags=["retros"])


@router.get("/retros")
def list_retros(session: DbSession) -> list[RetroOut]:
    retros = session.scalars(select(Retro).order_by(Retro.week_start.desc())).all()
    return [RetroOut.model_validate(retro) for retro in retros]


@router.get("/retros/latest")
def latest_retro(session: DbSession) -> RetroOut:
    retro = session.scalars(select(Retro).order_by(Retro.week_start.desc())).first()
    if retro is None:
        raise HTTPException(404, "no retro yet")
    return RetroOut.model_validate(retro)
