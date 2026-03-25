"""
services/date_validator.py
All deadline / due-date validation logic for the hub.
Each function returns a list of error strings (empty = valid).
"""
from datetime import datetime, date, timedelta


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_date(date_str):
    """Parse YYYY-MM-DD string → datetime, or None on failure."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d')
    except ValueError:
        return None


def fmt(dt):
    """Human-readable date string, or ''."""
    return dt.strftime('%d %B %Y') if dt else ''


def today_str():
    """Today as YYYY-MM-DD (for HTML input min=)."""
    return date.today().strftime('%Y-%m-%d')


def max_date_str(*dates):
    """
    Earliest non-None datetime from *dates, formatted as YYYY-MM-DD.
    Used as HTML input max= to cap the date picker.  Returns '' if all None.
    """
    valid = [d for d in dates if d is not None]
    if not valid:
        return ''
    return min(valid).strftime('%Y-%m-%d')


# ── Project dates ─────────────────────────────────────────────────────────────

def validate_project_dates(application_deadline, commencement_date, due_date,
                            existing_project=None):
    """
    Validate the three project date fields on create or edit.
    Rules:
      1. commencement_date  > application_deadline
      2. due_date           > commencement_date
      3. due_date           > application_deadline
      4. (edit) no existing milestone/task deadline may exceed new due_date - 1
    Returns list of error strings.
    """
    errors = []
    today = datetime.combine(date.today(), datetime.min.time())

    if application_deadline and application_deadline < today:
        errors.append(
            f'Application deadline ({fmt(application_deadline)}) cannot be in the past.'
        )

    if application_deadline and commencement_date:
        if commencement_date <= application_deadline:
            errors.append(
                f'Commencement date ({fmt(commencement_date)}) must be '
                f'after the application deadline ({fmt(application_deadline)}).'
            )

    if commencement_date and due_date:
        if due_date <= commencement_date:
            errors.append(
                f'Project due date ({fmt(due_date)}) must be '
                f'after the commencement date ({fmt(commencement_date)}).'
            )

    if application_deadline and due_date and not commencement_date:
        if due_date <= application_deadline:
            errors.append(
                f'Project due date ({fmt(due_date)}) must be '
                f'after the application deadline ({fmt(application_deadline)}).'
            )

    # On edit: make sure existing milestones / tasks still fit
    if existing_project and due_date and not errors:
        limit = due_date - timedelta(days=1)
        for m in existing_project.milestones.all():
            if m.deadline and m.deadline.date() > limit.date():
                errors.append(
                    f'Milestone "{m.title}" has a due date of {fmt(m.deadline)}, '
                    f'which is after the new limit of {fmt(limit)} '
                    f'(one day before the new project due date). '
                    f'Update or remove that milestone first.'
                )
        for t in existing_project.tasks.all():
            if t.due_date and t.due_date.date() > limit.date():
                errors.append(
                    f'Task "{t.title}" has a due date of {fmt(t.due_date)}, '
                    f'which is after the new limit of {fmt(limit)}. '
                    f'Update or remove that task first.'
                )

    return errors


# ── Milestone due date ────────────────────────────────────────────────────────

def validate_milestone_deadline(deadline, project):
    """
    Three rules for a milestone due date:

    Rule 1 — deadline must be ≤ project.due_date - 1 day.
    Rule 2 — milestones cannot be created until the application deadline
              has passed (project has officially begun).
    Rule 3 — milestone completion blocking is handled in the blueprint,
              not here (it is about task state, not dates).

    Returns list of error strings.
    """
    errors = []

    # Rule 2 — application deadline must have passed
    if project.application_deadline:
        if datetime.utcnow().date() <= project.application_deadline.date():
            days_left = (project.application_deadline.date() - datetime.utcnow().date()).days
            errors.append(
                f'Milestones cannot be created until the application deadline has passed '
                f'({fmt(project.application_deadline)}). '
                f'{days_left} day(s) remaining before the project commences.'
            )
            # Stop here — no point checking Rule 1 if project hasn't started
            return errors

    if deadline is None:
        if project.due_date:
            errors.append('Please set a due date for this milestone.')
        return errors

    today = datetime.combine(date.today(), datetime.min.time())
    if deadline < today:
        errors.append(f'Milestone due date ({fmt(deadline)}) cannot be in the past.')
        return errors

    # Rule 1 — must be before project due_date
    if project.due_date:
        limit = project.due_date - timedelta(days=1)
        if deadline.date() > limit.date():
            errors.append(
                f'Milestone due date ({fmt(deadline)}) must be on or before '
                f'{fmt(limit)} — one day before the project due date of '
                f'{fmt(project.due_date)}.'
            )

    return errors


# ── Task due date ─────────────────────────────────────────────────────────────

def validate_task_due_date(due_date, milestone, project):
    """
    Validate a task due date:
      - Cannot be in the past.
      - Cannot exceed the milestone due date.
      - Cannot exceed project.due_date - 1 day.
    Returns list of error strings.
    """
    errors = []
    if due_date is None:
        return errors

    today = datetime.combine(date.today(), datetime.min.time())
    if due_date < today:
        errors.append(f'Task due date ({fmt(due_date)}) cannot be in the past.')
        return errors

    if milestone.deadline and due_date.date() > milestone.deadline.date():
        errors.append(
            f'Task due date ({fmt(due_date)}) cannot be after the '
            f'milestone due date ({fmt(milestone.deadline)}).'
        )

    if project.due_date:
        limit = project.due_date - timedelta(days=1)
        if due_date.date() > limit.date():
            errors.append(
                f'Task due date ({fmt(due_date)}) cannot be after '
                f'{fmt(limit)} (one day before the project due date of '
                f'{fmt(project.due_date)}).'
            )

    return errors
