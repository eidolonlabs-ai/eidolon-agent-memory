"""
Autonomous background worker.

Loads enabled ScheduledTask rows from PostgreSQL and runs them via APScheduler.
Each job runs in its own DB session with full error isolation.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update

from eidolon_agent_memory.db.session import AsyncSessionLocal
from eidolon_agent_memory.models.task import ScheduledTask, TaskExecution

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_task(task_id: uuid.UUID, task_type: str, user_id: uuid.UUID, companion_id: uuid.UUID) -> None:
    """Execute a single task, recording execution history."""
    async with AsyncSessionLocal() as db:
        exec_row = TaskExecution(task_id=task_id, status="running")
        db.add(exec_row)
        await db.commit()
        exec_id = exec_row.id

    result_summary = ""
    error_msg = ""
    status = "completed"

    try:
        async with AsyncSessionLocal() as db:
            match task_type:
                case "diary":
                    from eidolon_agent_memory.services.cognitive import generate_diary
                    mem = await generate_diary(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"diary memory_id={mem.id}"

                case "dream":
                    from eidolon_agent_memory.services.cognitive import generate_dream
                    mem = await generate_dream(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"dream memory_id={mem.id}"

                case "musing":
                    from eidolon_agent_memory.services.cognitive import generate_musing
                    mem = await generate_musing(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"musing memory_id={mem.id}"

                case "insight":
                    from eidolon_agent_memory.services.cognitive import generate_insights
                    insights = await generate_insights(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"{len(insights)} insights generated"

                case "journal_refresh":
                    from eidolon_agent_memory.services.cognitive import refresh_journal
                    j = await refresh_journal(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"journal v{j.version} updated"

                case "decay":
                    from eidolon_agent_memory.services.decay import decay_edges
                    n = await decay_edges(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"{n} edges decayed"

                case "dedup":
                    from eidolon_agent_memory.services.decay import dedup_edges
                    n = await dedup_edges(db, user_id=user_id, companion_id=companion_id)
                    result_summary = f"{n} edges superseded"

                case "session_cleanup":
                    from eidolon_agent_memory.worker.cognitive import expire_idle_sessions
                    n = await expire_idle_sessions(db)
                    result_summary = f"{n} sessions expired"

                case _:
                    log.warning("Unknown task_type: %s", task_type)
                    result_summary = f"unknown task_type '{task_type}' — skipped"

    except Exception as exc:
        log.exception("Task %s failed: %s", task_type, exc)
        error_msg = str(exc)
        status = "failed"

    # Update execution record
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(TaskExecution)
            .where(TaskExecution.id == exec_id)
            .values(
                status=status,
                completed_at=datetime.now(timezone.utc),
                result_summary=result_summary,
                error=error_msg or None,
            )
        )
        await db.execute(
            update(ScheduledTask)
            .where(ScheduledTask.id == task_id)
            .values(last_run_at=datetime.now(timezone.utc))
        )
        await db.commit()

    log.info("Task %s (%s) → %s: %s", task_type, task_id, status, result_summary)


async def load_schedules() -> None:
    """Load all enabled ScheduledTask rows and register them with APScheduler."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScheduledTask).where(ScheduledTask.enabled.is_(True))
        )
        tasks = list(result.scalars().all())

    for task in tasks:
        job_id = f"task_{task.id}"
        if scheduler.get_job(job_id):
            continue  # Already registered

        trigger = CronTrigger.from_crontab(task.schedule, timezone=task.timezone)
        scheduler.add_job(
            _run_task,
            trigger=trigger,
            id=job_id,
            kwargs={
                "task_id": task.id,
                "task_type": task.task_type,
                "user_id": task.user_id,
                "companion_id": task.companion_id,
            },
            replace_existing=True,
        )
        log.info("Scheduled %s for user=%s companion=%s @ %s", task.task_type, task.user_id, task.companion_id, task.schedule)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("Starting Eidolon Agent Memory worker...")

    await load_schedules()
    scheduler.start()
    log.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    # Reload schedule every 5 minutes to pick up newly created tasks
    async def _reload_loop() -> None:
        while True:
            await asyncio.sleep(300)
            await load_schedules()

    await _reload_loop()


if __name__ == "__main__":
    asyncio.run(run())
