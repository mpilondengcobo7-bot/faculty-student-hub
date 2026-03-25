from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from models import Notification
from app import db

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/')
@login_required
def list_notifications():
    page = request.args.get('page', 1, type=int)
    notifs = current_user.notifications.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=10, error_out=False)
    return render_template('notifications/list.html', notifs=notifs)


@notifications_bp.route('/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notif.is_read = True
    db.session.commit()
    if notif.link:
        return redirect(notif.link)
    return redirect(url_for('notifications.list_notifications'))


@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return redirect(url_for('notifications.list_notifications'))


@notifications_bp.route('/api/unread-count')
@login_required
def unread_count():
    count = current_user.unread_notifications_count()
    return jsonify({'count': count})


@notifications_bp.route('/api/recent')
@login_required
def recent():
    notifs = current_user.notifications.filter_by(is_read=False).order_by(
        Notification.created_at.desc()
    ).limit(5).all()
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notif_type,
        'link': n.link,
        'created_at': n.created_at.strftime('%d %b %Y %H:%M')
    } for n in notifs]
    return jsonify(data)
