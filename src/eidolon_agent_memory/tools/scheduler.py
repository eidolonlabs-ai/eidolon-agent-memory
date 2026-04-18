"""
Scheduler tools: set_task_schedule, list_task_schedules, toggle_task,
run_task_now.

These tools let agents manage the autonomous background task schedule.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.task import ScheduledTask


VALID_TASK_TYPES = {
    "dream",
    "diary",
    "musing",
    "insight",
    "journal_refresh",
    "decay",
    "dedup",
    "session_cleanup",
}


async def tool_set_task_schedule(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    task_type: str,
    schedule: str,
    timezone: str = "UTC",
    config: dict | None = None,
) -> dict[str, Any]:
    """
    Create or update a scheduled autonomous task for a companion.

    task_type: dream | diary | musing | insight | journal_refresh | decay | dedup | session_cleanup
    schedule: cron expression e.g. "0 7 * * *" (7am daily)
    timezone: IANA timezone e.g. "America/New_York"

    Use for: user wants the companion to dream every morning, write daily diaries, etc.
    Do NOT use: for one-off tasks — call run_task_now instead.
    """
    if task_type not in VALID_TASK_TYPES:
        return {"error": f"Unknown task_type. Valid: {sorted(VALID_TASK_TYPES)}"}

    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.user_id == user_id,
            ScheduledTask.companion_id == companion_id,
            ScheduledTask.task_type == task_type,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        task = ScheduledTask(
            user_id=user_id,
            companion_id=companion_id,
            task_type=task_type,
            schedule=schedule,
            timezone=timezone,
            config=config,
            enabled=True,
        )
        db.add(task)
    else:
        task.schedule = schedule
        task.timezone = timezone
        task.enabled = True
        if config:
            task.config = {**(task.config or {}), **config}

    await db.commit()
    await db.refresh(task)
    return {
        "task_id": str(task.id),
        "task_type": task_type,
        "schedule": schedule,
        "timezone": timezone,
        "enabled": True,
    }


async def tool_list_task_schedules(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    List all scheduled tasks for a companion.
    """
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.user_id == user_id,
            ScheduledTask.companion_id == companion_id,
        )
    )
    tasks = list(result.scalars().all())
    return {
        "tasks": [
            {
                "task_id": str(t.id),
                "task_type": t.task_type,
                "schedule": t.schedule,
                "timezone": t.timezone,
                "enabled": t.enabled,
                "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
            }
            for t in tasks
        ],
        "count": len(tasks),
    }


async def tool_toggle_task(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    enabled: bool,
) -> dict[str, Any]:
    """
    Enable or disable a scheduled task.

    Use for: pausing/resuming a task without deleting its schedule.
    """
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.user_id == user_id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        return {"error": "task_not_found"}
    task.enabled = enabled
    await db.commit()
    return {"task_id": str(task.id), "enabled": enabled}


async def tool_run_task_now(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    task_type: str,
) -> dict[str, Any]:
    """
    Immediately execute a cognitive task (one-shot, not scheduled).

    task_type: dream | diary | musing | insight | journal_refresh
    Use for: user requests an on-demand diary entry, dream, etc.
    Do NOT use: for decay/dedup/cleanup — those should only run on schedule.
    """
    from eidolon_agent_memory.services.cognitive import (
        generate_diary,
        generate_dream,
        generate_insights,
        generate_musing,
        refresh_journal,
    )

    IMMEDIATE_TASKS = {"dream", "diary", "musing", "insight", "journal_refresh"}
    if task_type not in IMMEDIATE_TASKS:
        return {"error": f"task_type '{task_type}' cannot be run immediately"}

    match task_type:
        case "diary":
            result = await generate_diary(
                db, user_id=user_id, companion_id=companion_id
            )
            return {"task_type": "diary", "memory_id": str(result.id), "text": result.text[:200]}
        case "dream":
            result = await generate_dream(
                db, user_id=user_id, companion_id=companion_id
            )
            return {"task_type": "dream", "memory_id": str(result.id), "text": result.text[:200]}
        case "musing":
            result = await generate_musing(
                db, user_id=user_id, companion_id=companion_id
            )
            return {"task_type": "musing", "memory_id": str(result.id), "text": result.text[:200]}
        case "insight":
            insights = await generate_insights(
                db, user_id=user_id, companion_id=companion_id
            )
            return {"task_type": "insight", "count": len(insights)}
        case "journal_refresh":
            journal = await refresh_journal(
                db, user_id=user_id, companion_id=companion_id
            )
            return {
                "task_type": "journal_refresh",
                "journal_id": str(journal.id),
                "version": journal.version,
            }
        case _:
            return {"error": "unhandled task_type"}
