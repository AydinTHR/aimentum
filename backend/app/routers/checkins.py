from fastapi import APIRouter, HTTPException, UploadFile

from app.core.timeutil import user_today
from app.db import DbSession
from app.schemas import (
    EveningCheckinIn,
    EveningCheckinOut,
    MorningCheckinIn,
    MorningPlanOut,
    PlanOut,
    TaskOut,
    TranscriptOut,
)
from app.services import agent
from app.services.audio import (
    MAX_UPLOAD_BYTES,
    AudioError,
    AudioTooLargeError,
    FfmpegMissingError,
    transcode_to_flac,
)
from app.services.llm import LlmDep
from app.services.progress import progress_summary
from app.services.stt import SttDep

router = APIRouter(tags=["checkins"])


@router.post("/checkin/morning")
def morning_checkin(payload: MorningCheckinIn, session: DbSession, llm: LlmDep) -> MorningPlanOut:
    plan = agent.plan_morning(session, llm, payload.raw_text, payload.input_mode, user_today())
    session.commit()
    return MorningPlanOut(
        plan=PlanOut.model_validate(plan),
        tasks=[TaskOut.model_validate(task) for task in plan.tasks],
    )


@router.post("/checkin/morning/audio")
async def morning_audio(file: UploadFile, session: DbSession, stt: SttDep) -> TranscriptOut:
    """Transcode and transcribe only; the confirmed transcript then goes
    through POST /checkin/morning. Two steps on purpose: bad transcriptions
    get caught by a human before they become the day's plan."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        flac = transcode_to_flac(data)
    except AudioTooLargeError as error:
        raise HTTPException(413, str(error)) from error
    except FfmpegMissingError as error:
        raise HTTPException(500, str(error)) from error
    except AudioError as error:
        raise HTTPException(422, str(error)) from error
    transcript = stt.transcribe(flac)
    return TranscriptOut(transcript=transcript)


@router.post("/checkin/evening")
def evening_checkin(
    payload: EveningCheckinIn, session: DbSession, llm: LlmDep
) -> EveningCheckinOut:
    checkin = agent.submit_evening(
        session,
        llm,
        applications_sent=payload.applications_sent,
        note=payload.note,
        task_states=[(state.id, state.done) for state in payload.task_states],
        today=user_today(),
    )
    summary = progress_summary(session, user_today())
    session.commit()
    return EveningCheckinOut.model_validate({"checkin": checkin, "summary": summary})
