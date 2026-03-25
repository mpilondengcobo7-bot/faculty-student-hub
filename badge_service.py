"""
services/badge_service.py
Handles awarding badges and issuing completion certificates.
"""
import uuid
from datetime import datetime
from app import db
from models import (UserBadge, BadgeType, ProjectCertificate,
                    TaskSubmission, MilestoneStatus, ProjectStatus)
from services.notification_service import create_notification


# ── Internal helpers ──────────────────────────────────────────────────────────

def _already_has(user_id, badge_type, project_id=None):
    q = UserBadge.query.filter_by(user_id=user_id, badge_type=badge_type)
    if project_id:
        q = q.filter_by(project_id=project_id)
    return q.first() is not None


def _award(user_id, badge_type, project_id=None):
    """Award a badge if not already awarded. Returns badge or None."""
    if _already_has(user_id, badge_type, project_id):
        return None
    badge = UserBadge(user_id=user_id, badge_type=badge_type, project_id=project_id)
    db.session.add(badge)
    db.session.flush()

    meta = badge.meta
    create_notification(
        user_id=user_id,
        title=f'🏅 Badge Earned: {meta["label"]}',
        message=meta['desc'],
        notif_type='success',
        link='/achievements'
    )
    return badge


# ── Public triggers ───────────────────────────────────────────────────────────

def check_badges_on_join(user, project):
    """Call when a student is approved and added to a project."""
    _award(user.id, BadgeType.FIRST_STEP)

    joined_count = user.joined_projects.count()
    if joined_count >= 3:
        _award(user.id, BadgeType.TEAM_PLAYER)

    db.session.commit()


def check_badges_on_task_submit(user, project):
    """Call when a student submits a task."""
    subs = TaskSubmission.query.filter_by(student_id=user.id).count()
    if subs == 1:
        _award(user.id, BadgeType.QUICK_START)
    if subs >= 5:
        _award(user.id, BadgeType.OVERACHIEVER)
    db.session.commit()


def check_badges_on_feedback(submission):
    """Call when faculty gives feedback on a submission."""
    user_id = submission.student_id
    _award(user_id, BadgeType.COLLABORATOR)

    if submission.feedback and submission.feedback.rating == 5:
        _award(user_id, BadgeType.STAR_PERFORMER)

    db.session.commit()


def check_badges_on_milestone_complete(milestone, project):
    """
    Call when a milestone is marked completed.
    Award badges to every participating student based on their personal
    completed-milestone count across ALL projects.
    """
    for participant in project.participants:
        uid = participant.id

        # Count milestones completed in projects this student is part of
        from models import Milestone, project_participants
        completed_count = (
            Milestone.query
            .join(Milestone.project)
            .filter(
                Milestone.status == MilestoneStatus.COMPLETED,
                Milestone.project.has(
                    id=Milestone.project_id
                )
            )
            .count()
        )

        # Simpler: count all completed milestones in projects they joined
        from models import Project as Proj
        joined_project_ids = [p.id for p in participant.joined_projects.all()]
        if not joined_project_ids:
            continue

        from models import Milestone as MS
        done = MS.query.filter(
            MS.project_id.in_(joined_project_ids),
            MS.status == MilestoneStatus.COMPLETED
        ).count()

        if done >= 1:
            _award(uid, BadgeType.MILESTONE_1)
        if done >= 3:
            _award(uid, BadgeType.MILESTONE_3)
        if done >= 5:
            _award(uid, BadgeType.MILESTONE_5)

    db.session.commit()


def issue_project_certificates(project):
    """
    Call when faculty marks a project as COMPLETED.
    Issues a certificate to every approved participant and awards
    the PROJECT_DONE badge.
    """
    from services.email_service import send_certificate_email

    issued = []
    for participant in project.participants:
        # Skip if already issued
        existing = ProjectCertificate.query.filter_by(
            user_id=participant.id, project_id=project.id
        ).first()
        if existing:
            continue

        cert_number = f"DUT-{project.id:04d}-{participant.id:04d}-{uuid.uuid4().hex[:6].upper()}"
        cert = ProjectCertificate(
            user_id=participant.id,
            project_id=project.id,
            certificate_number=cert_number,
            issued_by=project.faculty.name
        )
        db.session.add(cert)
        db.session.flush()

        _award(participant.id, BadgeType.PROJECT_DONE, project_id=project.id)

        create_notification(
            user_id=participant.id,
            title='🎓 Certificate Issued!',
            message=f'Your completion certificate for "{project.title}" is ready.',
            notif_type='success',
            link=f'/achievements/certificate/{cert.id}'
        )

        try:
            send_certificate_email(participant, project, cert)
        except Exception:
            pass

        issued.append(cert)

    db.session.commit()
    return issued
