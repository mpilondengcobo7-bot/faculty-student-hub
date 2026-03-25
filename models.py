from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum


class UserRole(enum.Enum):
    STUDENT = 'student'
    FACULTY = 'faculty'
    ADMIN = 'admin'


class ProjectStatus(enum.Enum):
    OPEN = 'open'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'


class MilestoneStatus(enum.Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'


class ApplicationStatus(enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


# Association table: project participants
project_participants = db.Table(
    'project_participants',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(20), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    department = db.Column(db.String(100), nullable=True)
    avatar_url = db.Column(db.String(300), nullable=True)
    microsoft_id = db.Column(db.String(200), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    posted_projects = db.relationship('Project', backref='faculty', lazy='dynamic',
                                      foreign_keys='Project.faculty_id')
    applications = db.relationship('Application', backref='applicant', lazy='dynamic')
    task_submissions = db.relationship('TaskSubmission', backref='student', lazy='dynamic')
    documents = db.relationship('Document', backref='uploader', lazy='dynamic')
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic')
    feedback_given = db.relationship('Feedback', backref='faculty_member', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_faculty(self):
        return self.role == UserRole.FACULTY

    @property
    def is_student(self):
        return self.role == UserRole.STUDENT

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    def unread_notifications_count(self):
        return self.notifications.filter_by(is_read=False).count()

    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    objectives = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=True)
    department = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    application_deadline = db.Column(db.DateTime, nullable=True)  
    commencement_date    = db.Column(db.DateTime, nullable=True)
    due_date             = db.Column(db.DateTime, nullable=True)  
    max_participants     = db.Column(db.Integer, default=10)
    status = db.Column(db.Enum(ProjectStatus), default=ProjectStatus.OPEN)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    milestones = db.relationship('Milestone', backref='project', lazy='dynamic',
                                 cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='project', lazy='dynamic',
                                   cascade='all, delete-orphan')
    participants = db.relationship('User', secondary=project_participants,
                                   backref=db.backref('joined_projects', lazy='dynamic'))
    documents = db.relationship('Document', backref='project', lazy='dynamic')
    tasks = db.relationship('Task', backref='project', lazy='dynamic',
                            cascade='all, delete-orphan')

    def participant_count(self):
        return len(self.participants)

    def is_full(self):
        return self.participant_count() >= self.max_participants

    def completion_percentage(self):
        total = self.milestones.count()
        if total == 0:
            return 0
        done = self.milestones.filter_by(status=MilestoneStatus.COMPLETED).count()
        return int((done / total) * 100)

    def has_commenced(self):
        """True once the application deadline has passed (project accepting work)."""
        if not self.application_deadline:
            return True
        return datetime.utcnow().date() > self.application_deadline.date()

    def auto_advance_status(self):
        """
        Call on any page load to advance OPEN → IN_PROGRESS automatically
        once the application deadline has passed and participants exist.
        Returns True if status was changed.
        """
        if self.status == ProjectStatus.OPEN and self.has_commenced() and len(self.participants) > 0:
            self.status = ProjectStatus.IN_PROGRESS
            return True
        return False

    def milestone_deadline_limit(self):
        """Latest allowed milestone due date = project due_date minus 1 day."""
        if not self.due_date:
            return None
        from datetime import timedelta
        return self.due_date - timedelta(days=1)

    def __repr__(self):
        return f'<Project {self.title}>'


class Milestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.Enum(MilestoneStatus), default=MilestoneStatus.PENDING)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = db.relationship('Task', backref='milestone', lazy='dynamic',
                            cascade='all, delete-orphan')

    def all_tasks_completed(self):
        """True when every task under this milestone is marked complete."""
        total = self.tasks.count()
        if total == 0:
            return True        
        done = self.tasks.filter_by(is_completed=True).count()
        return done == total

    def incomplete_task_count(self):
        """Number of tasks not yet completed."""
        return self.tasks.filter_by(is_completed=False).count()

    def __repr__(self):
        return f'<Milestone {self.title}>'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestone.id'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('TaskSubmission', backref='task', lazy='dynamic',
                                  cascade='all, delete-orphan')
    assignee = db.relationship('User', foreign_keys=[assigned_to])

    def __repr__(self):
        return f'<Task {self.title}>'


class TaskSubmission(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    task_id           = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    student_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content           = db.Column(db.Text, nullable=True)            
    file_path         = db.Column(db.String(500), nullable=True)    
    original_filename = db.Column(db.String(300), nullable=True)    
    file_size         = db.Column(db.Integer, nullable=True)         
    file_type         = db.Column(db.String(10), nullable=True)      
    submitted_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    feedback = db.relationship('Feedback', backref='submission', uselist=False,
                               cascade='all, delete-orphan')

    @property
    def file_size_human(self):
        """Human-readable file size."""
        if not self.file_size:
            return ''
        size = self.file_size
        for unit in ('B', 'KB', 'MB'):
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} GB'

    @property
    def file_icon(self):
        """Bootstrap Icons name for this file type."""
        icons = {
            'pdf':  'file-earmark-pdf-fill',
            'doc':  'file-earmark-word-fill',
            'docx': 'file-earmark-word-fill',
            'ppt':  'file-earmark-ppt-fill',
            'pptx': 'file-earmark-ppt-fill',
            'png':  'file-earmark-image-fill',
            'jpg':  'file-earmark-image-fill',
            'jpeg': 'file-earmark-image-fill',
        }
        return icons.get((self.file_type or '').lower(), 'file-earmark-fill')

    @property
    def file_icon_color(self):
        """Accent colour for the file type icon."""
        colors = {
            'pdf':  '#ef4444',
            'doc':  '#2563eb', 'docx': '#2563eb',
            'ppt':  '#f97316', 'pptx': '#f97316',
            'png':  '#10b981', 'jpg':  '#10b981', 'jpeg': '#10b981',
        }
        return colors.get((self.file_type or '').lower(), '#6b7280')

    def __repr__(self):
        return f'<TaskSubmission task={self.task_id}>'


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('task_submission.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    feedback_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Feedback submission={self.submission_id}>'


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship('User', foreign_keys=[student_id],
                              backref=db.backref('project_applications', lazy='dynamic'))

    def __repr__(self):
        return f'<Application project={self.project_id} student={self.student_id}>'


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    backup_id = db.Column(db.Integer, db.ForeignKey('backup.id'), nullable=True)

    def __repr__(self):
        return f'<Document {self.original_name}>'


class Backup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    backup_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(300), nullable=True)
    documents = db.relationship('Document', backref='backup', lazy='dynamic')

    def __repr__(self):
        return f'<Backup {self.backup_date}>'


# ── Badges & Certificates ─────────────────────────────────────────────────────

class BadgeType(enum.Enum):
    FIRST_STEP     = 'first_step'       
    QUICK_START    = 'quick_start'      
    MILESTONE_1    = 'milestone_1'     
    MILESTONE_3    = 'milestone_3'     
    MILESTONE_5    = 'milestone_5'      
    TEAM_PLAYER    = 'team_player'      
    OVERACHIEVER   = 'overachiever'     
    COLLABORATOR   = 'collaborator'     
    STAR_PERFORMER = 'star_performer'   
    PROJECT_DONE   = 'project_done'     


BADGE_META = {
    BadgeType.FIRST_STEP:     {'label': 'First Step',      'icon': 'door-open',        'color': '#3b82f6', 'desc': 'Joined your first project'},
    BadgeType.QUICK_START:    {'label': 'Quick Start',     'icon': 'lightning-charge',  'color': '#f59e0b', 'desc': 'Submitted your first task'},
    BadgeType.MILESTONE_1:    {'label': 'Milestone Maker', 'icon': 'flag-fill',         'color': '#10b981', 'desc': 'Completed your first milestone'},
    BadgeType.MILESTONE_3:    {'label': 'On a Roll',       'icon': 'fire',              'color': '#ef4444', 'desc': 'Completed 3 milestones'},
    BadgeType.MILESTONE_5:    {'label': 'Milestone Master','icon': 'trophy-fill',       'color': '#8b5cf6', 'desc': 'Completed 5 milestones'},
    BadgeType.TEAM_PLAYER:    {'label': 'Team Player',     'icon': 'people-fill',       'color': '#06b6d4', 'desc': 'Joined 3 projects'},
    BadgeType.OVERACHIEVER:   {'label': 'Overachiever',    'icon': 'star-fill',         'color': '#f97316', 'desc': 'Completed 5 tasks'},
    BadgeType.COLLABORATOR:   {'label': 'Collaborator',    'icon': 'chat-left-heart',   'color': '#ec4899', 'desc': 'Received your first feedback'},
    BadgeType.STAR_PERFORMER: {'label': 'Star Performer',  'icon': 'patch-star-fill',   'color': '#eab308', 'desc': 'Received a 5-star feedback rating'},
    BadgeType.PROJECT_DONE:   {'label': 'Project Graduate','icon': 'mortarboard-fill',  'color': '#002147', 'desc': 'Part of a completed project'},
}


class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_type = db.Column(db.Enum(BadgeType), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('badges', lazy='dynamic'))
    project = db.relationship('Project', backref=db.backref('badges_awarded', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'badge_type', 'project_id', name='uq_user_badge_project'),
    )

    @property
    def meta(self):
        return BADGE_META.get(self.badge_type, {})

    def __repr__(self):
        return f'<UserBadge {self.badge_type.value} user={self.user_id}>'


class ProjectCertificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    certificate_number = db.Column(db.String(50), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    issued_by = db.Column(db.String(120), nullable=True)  

    user = db.relationship('User', backref=db.backref('certificates', lazy='dynamic'))
    project = db.relationship('Project', backref=db.backref('certificates', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'project_id', name='uq_user_project_cert'),
    )

    def __repr__(self):
        return f'<Certificate {self.certificate_number}>'


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notif_type = db.Column(db.String(50), default='info') 
    link = db.Column(db.String(300), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.title}>'


class TaskReminder(db.Model):
    """
    Tracks the last time a due-today reminder was sent to a student for a task.
    Prevents sending more than one reminder per 4-hour window.
    One record per (task_id, student_id) pair — upserted on each send.
    """
    __tablename__ = 'task_reminder'

    id         = db.Column(db.Integer, primary_key=True)
    task_id    = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    last_sent  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    task    = db.relationship('Task',
                              backref=db.backref('reminders', lazy='dynamic',
                                                 cascade='all, delete-orphan'))
    student = db.relationship('User',
                              backref=db.backref('task_reminders', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('task_id', 'student_id', name='uq_task_student_reminder'),
    )

    def __repr__(self):
        return f'<TaskReminder task={self.task_id} student={self.student_id}>'
