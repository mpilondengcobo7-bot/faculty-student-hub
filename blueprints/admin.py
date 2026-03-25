from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import User, Project, Application, UserRole, ProjectStatus
from app import db
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    role = request.args.get('role', '')
    search = request.args.get('q', '')
    query = User.query
    if role:
        try:
            query = query.filter_by(role=UserRole(role))
        except ValueError:
            pass
    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) | (User.email.ilike(f'%{search}%'))
        )
    users_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users_list, role=role, search=search)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.name} {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/change-role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    try:
        user.role = UserRole(new_role)
        db.session.commit()
        flash(f'{user.name} role changed to {new_role}.', 'success')
    except ValueError:
        flash('Invalid role.', 'danger')
    return redirect(url_for('admin.users'))


@admin_bp.route('/projects')
@login_required
@admin_required
def projects():
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('admin/projects.html', projects=all_projects)


@admin_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Project removed.', 'success')
    return redirect(url_for('admin.projects'))


# ── Scheduler admin ───────────────────────────────────────────────────────────

@admin_bp.route('/scheduler')
@login_required
@admin_required
def scheduler_status():
    """View scheduler jobs and their next run times."""
    from services.scheduler import _scheduler
    jobs = []
    if _scheduler:
        for job in _scheduler.get_jobs():
            jobs.append({
                'id':       job.id,
                'name':     job.name,
                'next_run': job.next_run_time.strftime('%d %b %Y %H:%M:%S UTC')
                            if job.next_run_time else 'N/A',
            })
    return render_template('admin/scheduler.html',
                           jobs=jobs,
                           running=bool(_scheduler and _scheduler.running))


@admin_bp.route('/scheduler/run-now', methods=['POST'])
@login_required
@admin_required
def scheduler_run_now():
    """Manually trigger the task-due reminder job immediately (for testing)."""
    from flask import current_app
    from services.scheduler import check_task_due_reminders
    try:
        check_task_due_reminders(current_app._get_current_object())
        flash('Reminder job executed successfully. Check logs and notifications.', 'success')
    except Exception as e:
        flash(f'Job failed: {e}', 'danger')
    return redirect(url_for('admin.scheduler_status'))
