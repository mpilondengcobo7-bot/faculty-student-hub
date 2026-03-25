import atexit
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()
oauth = OAuth()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)

    # Microsoft OAuth registration
    oauth.register(
        name='microsoft',
        client_id=app.config['MICROSOFT_CLIENT_ID'],
        client_secret=app.config['MICROSOFT_CLIENT_SECRET'],
        server_metadata_url=(
            f"https://login.microsoftonline.com/"
            f"{app.config['MICROSOFT_TENANT_ID']}/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={'scope': 'openid email profile User.Read'},
    )

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.projects import projects_bp
    from blueprints.milestones import milestones_bp
    from blueprints.notifications import notifications_bp
    from blueprints.admin import admin_bp
    from blueprints.achievements import achievements_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(milestones_bp, url_prefix='/milestones')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(achievements_bp, url_prefix='/achievements')

    # ── Custom Jinja2 filters ──────────────────────────────────────────────────
    @app.template_filter('strftime')
    def strftime_filter(dt, fmt='%d %b %Y'):
        if dt is None:
            return ''
        return dt.strftime(fmt)

    @app.template_filter('min')
    def min_filter(iterable):
        items = [i for i in iterable if i is not None]
        return min(items) if items else None

    # ── Background Scheduler (task due-today reminders) ────────────────────────
    # Guard: only start in the main process (not in Flask's reloader child)
    import os
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from services.scheduler import init_scheduler, shutdown_scheduler
        init_scheduler(app)
        atexit.register(shutdown_scheduler)

    # ── Upload folder ──────────────────────────────────────────────────────────
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads/submissions'), exist_ok=True)

    # ── 413 handler — file too large ───────────────────────────────────────────
    @app.errorhandler(413)
    def file_too_large(e):
        from flask import flash, redirect, request as req
        flash('File exceeds the 50 MB maximum size limit. Please upload a smaller file.', 'danger')
        return redirect(req.referrer or '/')

    return app
