import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import (Milestone, MilestoneStatus, Task, TaskSubmission, Feedback,
                    Project, ProjectStatus)
from app import db
from datetime import datetime
from services.email_service import send_feedback_notification
from services.notification_service import (notify_milestone_created,
                                           notify_milestone_completed,
                                           notify_feedback_given)
from services import badge_service
from services.date_validator import (parse_date, validate_milestone_deadline,
                                     validate_task_due_date, max_date_str, today_str)
from services.upload_service import (save_submission_file, delete_submission_file,
                                     submission_file_path)

milestones_bp = Blueprint('milestones', __name__)


# ── Guards ────────────────────────────────────────────────────────────────────

def require_faculty_of_project(project):
    if project.faculty_id != current_user.id and not current_user.is_admin:
        abort(403)


def require_participant_or_faculty(project):
    if current_user.is_admin:
        return
    if current_user.is_faculty and project.faculty_id == current_user.id:
        return
    if current_user.is_student and current_user in project.participants:
        return
    abort(403)


# ── Milestones ────────────────────────────────────────────────────────────────

@milestones_bp.route('/project/<int:project_id>/create', methods=['GET', 'POST'])
@login_required
def create(project_id):
    project = Project.query.get_or_404(project_id)
    require_faculty_of_project(project)

    # Compute the max date string for the date-picker cap
    limit_dt  = project.milestone_deadline_limit()
    max_dl    = max_date_str(limit_dt) if limit_dt else ''
    min_dl    = project.commencement_date.strftime('%Y-%m-%d') if project.commencement_date else today_str()

    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip() or None
        deadline    = parse_date(request.form.get('deadline', ''))

        errors = []
        if not title:
            errors.append('Milestone title is required.')

        # Run all date rules (Rule 1 + Rule 2)
        errors.extend(validate_milestone_deadline(deadline, project))

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('milestones/create.html', project=project,
                                   form_data=request.form,
                                   max_deadline=max_dl, min_deadline=min_dl,
                                   today=today_str())

        order = project.milestones.count() + 1
        milestone = Milestone(
            title=title, description=description,
            deadline=deadline, project_id=project_id, order=order
        )
        db.session.add(milestone)
        db.session.commit()
        notify_milestone_created(project, milestone)
        flash('Milestone created successfully.', 'success')
        return redirect(url_for('projects.detail', project_id=project_id))

    return render_template('milestones/create.html', project=project, form_data={},
                           max_deadline=max_dl, min_deadline=min_dl,
                           today=today_str())


@milestones_bp.route('/<int:milestone_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(milestone_id):
    milestone = Milestone.query.get_or_404(milestone_id)
    project   = milestone.project
    require_faculty_of_project(project)

    # Completed milestones are locked — no edits allowed
    if milestone.status == MilestoneStatus.COMPLETED:
        flash('Completed milestones cannot be edited.', 'warning')
        return redirect(url_for('projects.detail', project_id=project.id))

    limit_dt = project.milestone_deadline_limit()
    max_dl   = max_date_str(limit_dt) if limit_dt else ''
    min_dl   = project.commencement_date.strftime('%Y-%m-%d') if project.commencement_date else today_str()

    if request.method == 'POST':
        title       = request.form.get('title', milestone.title).strip()
        description = request.form.get('description', '').strip() or None
        deadline    = parse_date(request.form.get('deadline', ''))
        new_status_str = request.form.get('status', milestone.status.value)

        errors = validate_milestone_deadline(deadline, project)

        # Rule 3 — cannot mark complete unless ALL tasks are done
        try:
            new_status = MilestoneStatus(new_status_str)
        except ValueError:
            new_status = milestone.status

        if new_status == MilestoneStatus.COMPLETED and milestone.status != MilestoneStatus.COMPLETED:
            if not milestone.all_tasks_completed():
                n = milestone.incomplete_task_count()
                errors.append(
                    f'Cannot mark milestone as Completed: {n} task(s) still incomplete. '
                    f'All tasks must be completed first.'
                )

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('milestones/edit.html', milestone=milestone,
                                   max_deadline=max_dl, min_deadline=min_dl,
                                   today=today_str())

        milestone.title       = title
        milestone.description = description
        if deadline:
            milestone.deadline = deadline

        was_completed = milestone.status == MilestoneStatus.COMPLETED
        milestone.status = new_status
        db.session.commit()

        if new_status == MilestoneStatus.COMPLETED and not was_completed:
            notify_milestone_completed(milestone)
            badge_service.check_badges_on_milestone_complete(milestone, project)

        flash('Milestone updated.', 'success')
        return redirect(url_for('projects.detail', project_id=milestone.project_id))

    return render_template('milestones/edit.html', milestone=milestone,
                           max_deadline=max_dl, min_deadline=min_dl,
                           today=today_str())


@milestones_bp.route('/<int:milestone_id>/delete', methods=['POST'])
@login_required
def delete(milestone_id):
    milestone = Milestone.query.get_or_404(milestone_id)
    require_faculty_of_project(milestone.project)

    if milestone.status == MilestoneStatus.COMPLETED:
        flash('Cannot delete a completed milestone.', 'warning')
        return redirect(url_for('projects.detail', project_id=milestone.project_id))

    project_id = milestone.project_id
    db.session.delete(milestone)
    db.session.commit()
    flash('Milestone deleted.', 'success')
    return redirect(url_for('projects.detail', project_id=project_id))


@milestones_bp.route('/<int:milestone_id>/update-status', methods=['POST'])
@login_required
def update_status(milestone_id):
    """Quick status change from the project detail page."""
    milestone = Milestone.query.get_or_404(milestone_id)
    require_participant_or_faculty(milestone.project)
    new_status_str = request.form.get('status')

    try:
        new_status = MilestoneStatus(new_status_str)
    except ValueError:
        flash('Invalid status.', 'danger')
        return redirect(url_for('projects.detail', project_id=milestone.project_id))

    # Students can only move to in_progress, not completed
    if current_user.is_student and new_status == MilestoneStatus.COMPLETED:
        flash('Only faculty can mark a milestone as completed.', 'warning')
        return redirect(url_for('projects.detail', project_id=milestone.project_id))

    # Rule 3 — faculty completing must have all tasks done
    if new_status == MilestoneStatus.COMPLETED and milestone.status != MilestoneStatus.COMPLETED:
        if not milestone.all_tasks_completed():
            n = milestone.incomplete_task_count()
            flash(
                f'Cannot complete milestone: {n} task(s) still incomplete. '
                f'All tasks must be submitted first.',
                'danger'
            )
            return redirect(url_for('projects.detail', project_id=milestone.project_id))

    was_completed  = milestone.status == MilestoneStatus.COMPLETED
    milestone.status = new_status
    db.session.commit()

    if new_status == MilestoneStatus.COMPLETED and not was_completed:
        notify_milestone_completed(milestone)
        badge_service.check_badges_on_milestone_complete(milestone, milestone.project)

    flash('Milestone status updated.', 'success')
    return redirect(url_for('projects.detail', project_id=milestone.project_id))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@milestones_bp.route('/<int:milestone_id>/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task(milestone_id):
    milestone = Milestone.query.get_or_404(milestone_id)
    project   = milestone.project
    require_faculty_of_project(project)

    # Rule 3b — no new tasks on a completed milestone
    if milestone.status == MilestoneStatus.COMPLETED:
        flash('Cannot add tasks to a completed milestone.', 'warning')
        return redirect(url_for('projects.detail', project_id=milestone.project_id))

    limit_dt = project.milestone_deadline_limit()
    max_due  = max_date_str(milestone.deadline, limit_dt)

    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip() or None
        due_date    = parse_date(request.form.get('due_date', ''))
        assigned_id = request.form.get('assigned_to', type=int)

        errors = []
        if not title:
            errors.append('Task title is required.')
        errors.extend(validate_task_due_date(due_date, milestone, project))

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template(
                'milestones/create_task.html', milestone=milestone,
                participants=project.participants,
                form_data=request.form,
                max_due=max_due, today=today_str()
            )

        task = Task(
            title=title, description=description, due_date=due_date,
            project_id=milestone.project_id, milestone_id=milestone_id,
            assigned_to=assigned_id if assigned_id else None
        )
        db.session.add(task)
        db.session.commit()
        flash('Task created.', 'success')
        return redirect(url_for('projects.detail', project_id=milestone.project_id))

    return render_template(
        'milestones/create_task.html', milestone=milestone,
        participants=project.participants,
        max_due=max_due, today=today_str()
    )


@milestones_bp.route('/tasks/<int:task_id>/submit', methods=['POST'])
@login_required
def submit_task(task_id):
    from flask import current_app
    task = Task.query.get_or_404(task_id)
    if not current_user.is_student:
        abort(403)
    if current_user not in task.project.participants:
        abort(403)
    if task.assigned_to and task.assigned_to != current_user.id:
        flash('This task is assigned to another student.', 'warning')
        return redirect(url_for('projects.detail', project_id=task.project_id))

    content     = request.form.get('content', '').strip()
    upload_file = request.files.get('submission_file')
    is_new_sub  = False

    existing = TaskSubmission.query.filter_by(
        task_id=task_id, student_id=current_user.id).first()

    # ── Handle file upload ────────────────────────────────────────────────────
    file_data = None
    if upload_file and upload_file.filename:
        result = save_submission_file(upload_file)
        if not result['ok']:
            flash(result['error'], 'danger')
            return redirect(url_for('projects.detail', project_id=task.project_id))
        file_data = result

    # At least one of content or file must be provided
    if not content and not file_data and not (existing and (existing.file_path or existing.content)):
        flash('Please provide a text description or upload a file.', 'danger')
        return redirect(url_for('projects.detail', project_id=task.project_id))

    if existing:
        existing.content      = content or existing.content
        existing.submitted_at = datetime.utcnow()
        # Replace file if a new one was uploaded
        if file_data:
            delete_submission_file(existing.file_path)   # remove old file
            existing.file_path         = file_data['stored_name']
            existing.original_filename = file_data['original_name']
            existing.file_size         = file_data['file_size']
            existing.file_type         = file_data['file_type']
        db.session.commit()
        flash('Submission updated.', 'success')
    else:
        sub = TaskSubmission(
            task_id=task_id,
            student_id=current_user.id,
            content=content or None,
        )
        if file_data:
            sub.file_path         = file_data['stored_name']
            sub.original_filename = file_data['original_name']
            sub.file_size         = file_data['file_size']
            sub.file_type         = file_data['file_type']
        db.session.add(sub)
        task.is_completed = True
        db.session.commit()
        badge_service.check_badges_on_task_submit(current_user, task.project)
        flash('Task submitted successfully.', 'success')

    return redirect(url_for('projects.detail', project_id=task.project_id))


@milestones_bp.route('/submissions/<int:sub_id>/download')
@login_required
def download_submission(sub_id):
    """Faculty (project owner) or the submitting student can download a submission file."""
    from flask import send_file
    sub  = TaskSubmission.query.get_or_404(sub_id)
    task = sub.task

    # Access control
    is_owner_faculty = (current_user.is_faculty and task.project.faculty_id == current_user.id)
    is_submitter     = (current_user.id == sub.student_id)
    if not (is_owner_faculty or is_submitter or current_user.is_admin):
        abort(403)

    if not sub.file_path:
        flash('No file attached to this submission.', 'warning')
        return redirect(url_for('projects.detail', project_id=task.project_id))

    file_full_path = submission_file_path(sub.file_path)
    if not os.path.isfile(file_full_path):
        flash('File not found on server. It may have been removed.', 'danger')
        return redirect(url_for('projects.detail', project_id=task.project_id))

    return send_file(
        file_full_path,
        as_attachment=True,
        download_name=sub.original_filename or sub.file_path,
    )


@milestones_bp.route('/tasks/<int:task_id>/feedback', methods=['POST'])
@login_required
def give_feedback(task_id):
    task = Task.query.get_or_404(task_id)
    if not current_user.is_faculty or task.project.faculty_id != current_user.id:
        abort(403)

    submission_id = request.form.get('submission_id', type=int)
    submission    = TaskSubmission.query.get_or_404(submission_id)

    if submission.feedback:
        submission.feedback.comment       = request.form.get('comment', '').strip()
        submission.feedback.rating        = request.form.get('rating', type=int)
        submission.feedback.feedback_date = datetime.utcnow()
        db.session.commit()
    else:
        fb = Feedback(
            submission_id=submission_id,
            faculty_id=current_user.id,
            comment=request.form.get('comment', '').strip(),
            rating=request.form.get('rating', type=int)
        )
        db.session.add(fb)
        db.session.commit()
        badge_service.check_badges_on_feedback(submission)

    try:
        send_feedback_notification(submission)
    except Exception:
        pass
    notify_feedback_given(submission)
    flash('Feedback submitted.', 'success')
    return redirect(url_for('projects.detail', project_id=task.project_id))
