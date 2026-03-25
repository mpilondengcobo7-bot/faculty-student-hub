from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import (Project, ProjectStatus, Application, ApplicationStatus,
                    Milestone, MilestoneStatus, Task, TaskSubmission,
                    User, UserRole, ProjectCertificate)
from datetime import datetime, timedelta
from app import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    now = datetime.utcnow()

    if current_user.is_faculty:
        projects = current_user.posted_projects.order_by(Project.created_at.desc()).limit(5).all()
        pending_apps = Application.query.join(Project).filter(
            Project.faculty_id == current_user.id,
            Application.status == ApplicationStatus.PENDING
        ).count()
        total_projects = current_user.posted_projects.count()
        active_projects = current_user.posted_projects.filter_by(status=ProjectStatus.IN_PROGRESS).count()

        upcoming_milestones = Milestone.query.join(Project).filter(
            Project.faculty_id == current_user.id,
            Milestone.deadline.isnot(None),
            Milestone.deadline > now,
            Milestone.deadline <= now + timedelta(days=7),
            Milestone.status != MilestoneStatus.COMPLETED
        ).order_by(Milestone.deadline).limit(5).all()
        return render_template('main/faculty_dashboard.html',
                               projects=projects,
                               pending_apps=pending_apps,
                               total_projects=total_projects,
                               active_projects=active_projects,
                               upcoming_milestones=upcoming_milestones)

    elif current_user.is_student:
        joined = current_user.joined_projects.filter(
            Project.status != ProjectStatus.ARCHIVED
        ).order_by(Project.updated_at.desc()).limit(5).all()
        pending_apps = current_user.project_applications.filter_by(
            status=ApplicationStatus.PENDING
        ).count()
        upcoming_milestones = Milestone.query.join(Project).filter(
            Project.participants.any(id=current_user.id),
            Milestone.deadline.isnot(None),
            Milestone.deadline > now,
            Milestone.deadline <= now + timedelta(days=7),
            Milestone.status != MilestoneStatus.COMPLETED
        ).order_by(Milestone.deadline).limit(5).all()
        open_projects = Project.query.filter_by(status=ProjectStatus.OPEN).count()

        # Tasks due TODAY that the student has not yet submitted
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end   = datetime.combine(date.today(), datetime.max.time())

        # Get IDs of tasks the student already submitted
        submitted_task_ids = [
            s.task_id for s in TaskSubmission.query.filter_by(
                student_id=current_user.id
            ).all()
        ]

        # Tasks in projects the student participates in, due today, not yet submitted
        tasks_due_today = Task.query.join(Project).filter(
            Project.participants.any(id=current_user.id),
            Task.is_completed == False,
            Task.due_date >= today_start,
            Task.due_date <= today_end,
            Task.id.notin_(submitted_task_ids) if submitted_task_ids else True,
        ).filter(
           
            db.or_(Task.assigned_to == None, Task.assigned_to == current_user.id)
        ).order_by(Task.due_date).all()

        return render_template('main/student_dashboard.html',
                               joined=joined,
                               pending_apps=pending_apps,
                               upcoming_milestones=upcoming_milestones,
                               open_projects=open_projects,
                               tasks_due_today=tasks_due_today)

    elif current_user.is_admin:
        total_users = User.query.count()
        total_projects = Project.query.count()
        total_students = User.query.filter_by(role=UserRole.STUDENT).count()
        total_faculty = User.query.filter_by(role=UserRole.FACULTY).count()
        recent_projects = Project.query.order_by(Project.created_at.desc()).limit(10).all()
        pending_apps = Application.query.filter_by(status=ApplicationStatus.PENDING).count()
        return render_template('main/admin_dashboard.html',
                               total_users=total_users,
                               total_projects=total_projects,
                               total_students=total_students,
                               total_faculty=total_faculty,
                               recent_projects=recent_projects,
                               pending_apps=pending_apps)

    return redirect(url_for('auth.login'))
