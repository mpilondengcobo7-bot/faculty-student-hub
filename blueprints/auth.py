from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db, oauth
from models import User, UserRole
from datetime import datetime
from services.email_service import send_welcome_email

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        user = User.query.filter_by(email=email).first()
        if user and user.password_hash and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Contact admin.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        role_str = request.form.get('role', 'student')
        student_number = request.form.get('student_number', '').strip() or None
        department = request.form.get('department', '').strip() or None

        # POPIA acceptance check
        if not request.form.get('popia_accepted'):
            flash('You must accept the POPIA Declaration to register.', 'danger')
            return redirect(url_for('auth.register'))

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))

        try:
            role = UserRole(role_str)
        except ValueError:
            role = UserRole.STUDENT

        user = User(name=name, email=email, role=role,
                    student_number=student_number, department=department)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        try:
            send_welcome_email(user)
        except Exception:
            pass
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ── Microsoft OAuth ───────────────────────────────────────────────────────────

@auth_bp.route('/microsoft/login')
def microsoft_login():
    redirect_uri = url_for('auth.microsoft_callback', _external=True)
    return oauth.microsoft.authorize_redirect(redirect_uri)


@auth_bp.route('/microsoft/callback')
def microsoft_callback():
    try:
        token = oauth.microsoft.authorize_access_token()
        userinfo = token.get('userinfo') or oauth.microsoft.userinfo()
        ms_id = userinfo.get('sub') or userinfo.get('oid')
        email = userinfo.get('email') or userinfo.get('preferred_username', '')
        name = userinfo.get('name', email.split('@')[0])

        user = User.query.filter_by(microsoft_id=ms_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
            if user:
                user.microsoft_id = ms_id
            else:

                role = UserRole.FACULTY if 'staff' in email or 'faculty' in email else UserRole.STUDENT
                user = User(name=name, email=email, microsoft_id=ms_id, role=role)
                db.session.add(user)
                db.session.flush()
                try:
                    send_welcome_email(user)
                except Exception:
                    pass
        user.last_login = datetime.utcnow()
        db.session.commit()

        if not user.is_active:
            flash('Your account has been deactivated.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=True)
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        current_app.logger.error(f"Microsoft OAuth error: {e}")
        flash('Microsoft login failed. Please try again.', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name).strip()
        current_user.department = request.form.get('department', '').strip() or None
        if request.form.get('new_password'):
            if not current_user.check_password(request.form.get('current_password', '')):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('auth.profile'))
            current_user.set_password(request.form.get('new_password'))
        db.session.commit()
        flash('Profile updated.', 'success')
    return render_template('auth/profile.html')
