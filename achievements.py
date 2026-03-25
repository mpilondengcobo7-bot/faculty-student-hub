from flask import Blueprint, render_template, abort, make_response
from flask_login import login_required, current_user
from models import UserBadge, ProjectCertificate, BadgeType, BADGE_META, User
from app import db

achievements_bp = Blueprint('achievements', __name__)


@achievements_bp.route('/')
@login_required
def index():
    """Personal achievements wall — badges + certificates."""
    earned_badges = current_user.badges.order_by(UserBadge.awarded_at.desc()).all()
    earned_types = {b.badge_type for b in earned_badges}

    # Build full badge grid: earned + locked
    all_badges = []
    for badge_type, meta in BADGE_META.items():
        earned = next((b for b in earned_badges if b.badge_type == badge_type), None)
        all_badges.append({
            'type': badge_type,
            'meta': meta,
            'earned': earned,
            'locked': earned is None
        })

    certificates = current_user.certificates.order_by(
        ProjectCertificate.issued_at.desc()
    ).all()

    return render_template('achievements/index.html',
                           all_badges=all_badges,
                           earned_count=len(earned_types),
                           total_badges=len(BADGE_META),
                           certificates=certificates)


@achievements_bp.route('/certificate/<int:cert_id>')
@login_required
def view_certificate(cert_id):
    cert = ProjectCertificate.query.get_or_404(cert_id)
    if cert.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template('achievements/certificate.html', cert=cert)


@achievements_bp.route('/certificate/<int:cert_id>/print')
@login_required
def print_certificate(cert_id):
    cert = ProjectCertificate.query.get_or_404(cert_id)
    if cert.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template('achievements/certificate_print.html', cert=cert)


@achievements_bp.route('/user/<int:user_id>')
@login_required
def user_achievements(user_id):
    """Faculty/Admin can view a student's achievements."""
    user = User.query.get_or_404(user_id)
    earned_badges = user.badges.order_by(UserBadge.awarded_at.desc()).all()
    earned_types = {b.badge_type for b in earned_badges}

    all_badges = []
    for badge_type, meta in BADGE_META.items():
        earned = next((b for b in earned_badges if b.badge_type == badge_type), None)
        all_badges.append({'type': badge_type, 'meta': meta,
                           'earned': earned, 'locked': earned is None})

    certificates = user.certificates.order_by(ProjectCertificate.issued_at.desc()).all()
    return render_template('achievements/index.html',
                           all_badges=all_badges,
                           earned_count=len(earned_types),
                           total_badges=len(BADGE_META),
                           certificates=certificates,
                           profile_user=user)
