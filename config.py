import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///hub.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Mail (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.office365.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@dut.ac.za')

    # Microsoft OAuth (Azure AD)
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID', '')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET', '')
    MICROSOFT_TENANT_ID = os.environ.get('MICROSOFT_TENANT_ID', 'common')

    # Pagination
    PROJECTS_PER_PAGE = 9
    NOTIFICATIONS_PER_PAGE = 10

    # File uploads
    UPLOAD_FOLDER       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'submissions')
    MAX_CONTENT_LENGTH  = 50 * 1024 * 1024   # 50 MB hard limit
    ALLOWED_EXTENSIONS  = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'png', 'jpeg', 'jpg'}
