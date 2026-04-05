from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from models import (Project, ProjectStatus, Application, ApplicationStatus,
                    User, UserRole, project_participants)
from app import db
from datetime import datetime
from services.email_service import send_application_notification, send_application_result
from services.notification_service import (notify_application_received,
                                           notify_application_result, notify_new_project)
from services import badge_service
from services.date_validator import (parse_date, validate_project_dates,
                                     max_date_str, today_str)

projects_bp = Blueprint('projects', __name__)


def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_faculty:
            flash('Only faculty members can perform this action.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_student:
            flash('Only students can perform this action.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@projects_bp.route('/')
@login_required
def list_projects():
    page = request.args.get('page', 1, type=int)
    dept = request.args.get('dept', '')
    category = request.args.get('category', '')
    status_filter = request.args.get('status', 'open')
    search = request.args.get('q', '')

    query = Project.query
    if status_filter and status_filter != 'all':
        try:
            query = query.filter_by(status=ProjectStatus(status_filter))
        except ValueError:
            pass
    if dept:
        query = query.filter_by(department=dept)
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(Project.title.ilike(f'%{search}%'))

    projects = query.order_by(Project.created_at.desc()).paginate(
        page=page, per_page=current_app.config['PROJECTS_PER_PAGE'], error_out=False
    )
    departments = db.session.query(Project.department).filter(
        Project.department.isnot(None)).distinct().all()
    categories = db.session.query(Project.category).filter(
        Project.category.isnot(None)).distinct().all()

    return render_template('projects/list.html', projects=projects,
                           departments=[d[0] for d in departments],
                           categories=[c[0] for c in categories],
                           status_filter=status_filter, dept=dept,
                           category=category, search=search)


@projects_bp.route('/<int:project_id>')
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)

    # Auto-advance OPEN → IN_PROGRESS once application deadline passes
    if project.auto_advance_status():
        db.session.commit()
    is_participant = current_user in project.participants
    user_application = None
    if current_user.is_student:
        user_application = Application.query.filter_by(
            project_id=project_id, student_id=current_user.id
        ).first()
    milestones = project.milestones.order_by('order').all()
    return render_template('projects/detail.html', project=project,
                           is_participant=is_participant,
                           user_application=user_application,
                           milestones=milestones)


@projects_bp.route('/create', methods=['GET', 'POST'])
@login_required
@faculty_required
def create():
    if request.method == 'POST':
        application_deadline = parse_date(request.form.get('application_deadline', ''))
        commencement_date    = parse_date(request.form.get('commencement_date', ''))
        due_date             = parse_date(request.form.get('due_date', ''))

        errors = validate_project_dates(application_deadline, commencement_date, due_date)
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('projects/create.html',
                                   form_data=request.form, today=today_str())

        project = Project(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            objectives=request.form.get('objectives', '').strip() or None,
            requirements=request.form.get('requirements', '').strip() or None,
            department=request.form.get('department', '').strip() or None,
            category=request.form.get('category', '').strip() or None,
            application_deadline=application_deadline,
            commencement_date=commencement_date,
            due_date=due_date,
            max_participants=int(request.form.get('max_participants', 10)),
            faculty_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        students = User.query.filter_by(role=UserRole.STUDENT, is_active=True).all()
        notify_new_project(project, students)
        flash('Project posted successfully!', 'success')
        return redirect(url_for('projects.detail', project_id=project.id))
    return render_template('projects/create.html', today=today_str())


@projects_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
@faculty_required
def edit(project_id):
    project = Project.query.get_or_404(project_id)
    if project.faculty_id != current_user.id and not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        project.title = request.form.get('title', project.title).strip()
        project.description = request.form.get('description', project.description).strip()
        project.objectives = request.form.get('objectives', '').strip() or None
        project.requirements = request.form.get('requirements', '').strip() or None
        project.department = request.form.get('department', '').strip() or None
        project.category = request.form.get('category', '').strip() or None
        project.max_participants = int(request.form.get('max_participants', project.max_participants))

        new_app_dl  = parse_date(request.form.get('application_deadline', ''))
        new_comm    = parse_date(request.form.get('commencement_date', ''))
        new_due     = parse_date(request.form.get('due_date', ''))

        errors = validate_project_dates(new_app_dl, new_comm, new_due,
                                        existing_project=project)
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('projects/edit.html', project=project,
                                   today=today_str())

        project.application_deadline = new_app_dl
        project.commencement_date    = new_comm
        project.due_date             = new_due
        try:
            project.status = ProjectStatus(request.form.get('status', project.status.value))
        except ValueError:
            pass
        db.session.commit()
        flash('Project updated.', 'success')
        return redirect(url_for('projects.detail', project_id=project.id))
    return render_template('projects/edit.html', project=project, today=today_str())


@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
@faculty_required
def delete(project_id):
    project = Project.query.get_or_404(project_id)
    if project.faculty_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted.', 'success')
    return redirect(url_for('projects.list_projects'))


# ── Applications ─────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/apply', methods=['POST'])
@login_required
@student_required
def apply(project_id):
    project = Project.query.get_or_404(project_id)
    if project.status != ProjectStatus.OPEN:
        flash('This project is not accepting applications.', 'warning')
        return redirect(url_for('projects.detail', project_id=project_id))
    if project.is_full():
        flash('This project has reached its maximum participants.', 'warning')
        return redirect(url_for('projects.detail', project_id=project_id))
    existing = Application.query.filter_by(
        project_id=project_id, student_id=current_user.id
    ).first()
    if existing:
        flash('You have already applied to this project.', 'info')
        return redirect(url_for('projects.detail', project_id=project_id))
    if current_user in project.participants:
        flash('You are already a participant.', 'info')
        return redirect(url_for('projects.detail', project_id=project_id))

    app_obj = Application(
        project_id=project_id,
        student_id=current_user.id,
        message=request.form.get('message', '').strip() or None
    )
    db.session.add(app_obj)
    db.session.commit()
    try:
        send_application_notification(app_obj)
    except Exception:
        pass
    notify_application_received(app_obj)
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('projects.detail', project_id=project_id))


@projects_bp.route('/<int:project_id>/applications')
@login_required
@faculty_required
def applications(project_id):
    project = Project.query.get_or_404(project_id)
    if project.faculty_id != current_user.id and not current_user.is_admin:
        abort(403)
    pending = Application.query.filter_by(project_id=project_id,
                                          status=ApplicationStatus.PENDING).all()
    reviewed = Application.query.filter(
        Application.project_id == project_id,
        Application.status != ApplicationStatus.PENDING
    ).all()
    return render_template('projects/applications.html', project=project,
                           pending=pending, reviewed=reviewed)


@projects_bp.route('/applications/<int:app_id>/review', methods=['POST'])
@login_required
@faculty_required
def review_application(app_id):
    app_obj = Application.query.get_or_404(app_id)
    project = app_obj.project
    if project.faculty_id != current_user.id:
        abort(403)
    action = request.form.get('action')
    if action == 'approve':
        app_obj.status = ApplicationStatus.APPROVED
        app_obj.reviewed_at = datetime.utcnow()
        if app_obj.applicant not in project.participants:
            project.participants.append(app_obj.applicant)
            
            # Only move to IN_PROGRESS once the application deadline has passed
            if project.status == ProjectStatus.OPEN and project.has_commenced():
                project.status = ProjectStatus.IN_PROGRESS
        db.session.commit()
        try:
            send_application_result(app_obj)
        except Exception:
            pass
        notify_application_result(app_obj)
        badge_service.check_badges_on_join(app_obj.applicant, project)
        flash(f'{app_obj.applicant.name} approved and added to project.', 'success')
    elif action == 'reject':
        app_obj.status = ApplicationStatus.REJECTED
        app_obj.reviewed_at = datetime.utcnow()
        db.session.commit()
        try:
            send_application_result(app_obj)
        except Exception:
            pass
        notify_application_result(app_obj)
        flash(f'Application by {app_obj.applicant.name} rejected.', 'info')
    return redirect(url_for('projects.applications', project_id=project.id))


@projects_bp.route('/<int:project_id>/complete', methods=['POST'])
@login_required
def complete_project(project_id):
    """Faculty marks project as completed → issues certificates to all participants."""
    project = Project.query.get_or_404(project_id)
    if project.faculty_id != current_user.id and not current_user.is_admin:
        abort(403)
    project.status = ProjectStatus.COMPLETED
    db.session.commit()
    issued = badge_service.issue_project_certificates(project)
    n = len(issued)
    if n > 0:
        flash(f'🎓 Project completed! {n} certificate(s) issued to participants.', 'success')
    else:
        flash('Project marked as completed. Certificates already issued.', 'info')
    return redirect(url_for('projects.detail', project_id=project_id))
