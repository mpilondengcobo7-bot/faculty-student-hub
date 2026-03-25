"""
services/scheduler.py
──────────────────────
Background scheduler using APScheduler.

Job: check_task_due_reminders
  Runs every 4 hours.
  For every incomplete task whose due_date is TODAY:
    - Find every student who should submit it (all participants, or the assigned student).
    - If no submission exists AND the last reminder for that (task, student) pair
      was sent more than 4 hours ago (or never), send both an in-app notification
      and an email, then upsert the TaskReminder record.
"""

import logging
from datetime import datetime, timedelta, date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None   # module-level singleton


# ── Main job ──────────────────────────────────────────────────────────────────

def check_task_due_reminders(app):
    """
    Core reminder job.  Must be called with the Flask app so we can push
    an app context (APScheduler runs in its own thread).
    """
    with app.app_context():
        try:
            _run_reminder_check()
        except Exception:
            logger.exception("Error in check_task_due_reminders job")


def _run_reminder_check():
    from app import db
    from models import Task, TaskSubmission, TaskReminder, project_participants
    from services.notification_service import create_notification
    from services.email_service import send_task_due_reminder_email

    now   = datetime.utcnow()
    today = date.today()
    cutoff_4h = now - timedelta(hours=4)

    # All incomplete tasks due today
    tasks_due_today = (
        Task.query
        .filter(
            Task.is_completed == False,                        # noqa: E712
            db.func.date(Task.due_date) == today,
        )
        .all()
    )

    if not tasks_due_today:
        logger.info("Reminder job: no incomplete tasks due today.")
        return

    logger.info(f"Reminder job: found {len(tasks_due_today)} incomplete task(s) due today.")

    for task in tasks_due_today:
        project = task.project

        # Build list of students who need to submit this task
        if task.assigned_to:
            # Only the assigned student
            from models import User
            student = User.query.get(task.assigned_to)
            target_students = [student] if student else []
        else:
            # All participants of the project
            target_students = list(project.participants)

        for student in target_students:
            # Skip if already submitted
            already_submitted = TaskSubmission.query.filter_by(
                task_id=task.id,
                student_id=student.id
            ).first()
            if already_submitted:
                continue

            # Check the 4-hour cooldown
            reminder = TaskReminder.query.filter_by(
                task_id=task.id,
                student_id=student.id
            ).first()

            if reminder and reminder.last_sent >= cutoff_4h:
                # Already reminded within the last 4 hours — skip
                logger.debug(
                    f"Skipping reminder for student {student.id} / task {task.id} "
                    f"(last sent {reminder.last_sent})"
                )
                continue

            # ── Send in-app notification ──────────────────────────────────────
            project_link = f"/projects/{project.id}"
            create_notification(
                user_id=student.id,
                title="⏰ Task Due Today",
                message=(
                    f"Task \"{task.title}\" in project \"{project.title}\" "
                    f"is due today. Please submit your work before midnight."
                ),
                notif_type="warning",
                link=project_link,
            )

            # ── Send email reminder ───────────────────────────────────────────
            try:
                send_task_due_reminder_email(student, task, project)
            except Exception:
                logger.exception(
                    f"Failed to send email reminder to {student.email} "
                    f"for task {task.id}"
                )

            # ── Upsert TaskReminder record ────────────────────────────────────
            if reminder:
                reminder.last_sent = now
            else:
                reminder = TaskReminder(
                    task_id=task.id,
                    student_id=student.id,
                    last_sent=now
                )
                db.session.add(reminder)

            logger.info(
                f"Reminder sent → student: {student.name} ({student.email}), "
                f"task: \"{task.title}\", project: \"{project.title}\""
            )

    db.session.commit()


# ── Scheduler lifecycle ───────────────────────────────────────────────────────

def init_scheduler(app):
    """
    Start the APScheduler background scheduler.
    Safe to call multiple times — only starts once.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        return  # Already running (e.g. Flask reloader spawned a second process)

    _scheduler = BackgroundScheduler(
        job_defaults={
            'coalesce':       True,   # merge missed runs into one
            'max_instances':  1,      # never run the same job twice in parallel
            'misfire_grace_time': 60, # tolerate up to 60 s of lateness
        }
    )

    _scheduler.add_job(
        func=check_task_due_reminders,
        trigger=IntervalTrigger(hours=4),
        id='task_due_reminders',
        name='Task due-today reminder (every 4 hours)',
        replace_existing=True,
        kwargs={'app': app},
        # Run once immediately on startup so we don't wait 4 hours for first check
        next_run_time=datetime.now(),
    )

    _scheduler.start()
    logger.info("APScheduler started — task-due reminder job active (every 4 h).")


def shutdown_scheduler():
    """Gracefully stop the scheduler on app exit."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
