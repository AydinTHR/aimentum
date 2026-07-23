from fastapi import APIRouter, HTTPException

from app.core.timeutil import user_today
from app.db import DbSession
from app.models import Task
from app.schemas import TaskOut, TaskPatch
from app.services.progress import sync_task_progress

router = APIRouter(tags=["tasks"])


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, payload: TaskPatch, session: DbSession) -> TaskOut:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    if task.done != payload.done:
        task.done = payload.done
        sync_task_progress(session, task, payload.done, user_today())
    session.commit()
    return TaskOut.model_validate(task)
