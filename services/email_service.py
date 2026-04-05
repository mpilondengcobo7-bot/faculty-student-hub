from flask import current_app, render_template_string
from flask_mail import Message
from app import mail
from threading import Thread


def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f"Email send error: {e}")


def send_email(subject, recipients, html_body, text_body=None):
    """Send an email asynchronously."""
    app = current_app._get_current_object()
    msg = Message(
        subject=subject,
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=recipients if isinstance(recipients, list) else [recipients]
    )
    msg.html = html_body
    if text_body:
        msg.body = text_body
    t = Thread(target=send_async_email, args=[app, msg])
    t.daemon = True
    t.start()


# ── Email Templates ──────────────────────────────────────────────────────────

def send_welcome_email(user):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#003366;padding:30px;text-align:center;">
        <h1 style="color:white;margin:0;">DUT Project Hub</h1>
        <p style="color:#aac4ff;margin:5px 0 0;">Faculty–Student Collaborative Platform</p>
      </div>
      <div style="padding:30px;background:#f9f9f9;">
        <h2>Welcome, {user.name}!</h2>
        <p>Your account has been created successfully as a <strong>{user.role.value.capitalize()}</strong>.</p>
        <p>You can now log in and {'post projects, define milestones, and manage student collaboration.' if user.is_faculty else 'browse projects, apply to join, and track your milestones.'}</p>
        <a href="#" style="display:inline-block;background:#003366;color:white;padding:12px 28px;
           border-radius:6px;text-decoration:none;margin-top:15px;">Get Started</a>
      </div>
      <div style="padding:15px;text-align:center;color:#888;font-size:12px;">
        Durban University of Technology · Faculty of Accounting &amp; Informatics
      </div>
    </div>
    """
    send_email(f"Welcome to DUT Project Hub, {user.name}!", user.email, html)


def send_application_notification(application):
    project = application.project
    student = application.applicant
    faculty = project.faculty
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#003366;padding:25px;text-align:center;">
        <h2 style="color:white;margin:0;">New Project Application</h2>
      </div>
      <div style="padding:25px;">
        <p>Hi <strong>{faculty.name}</strong>,</p>
        <p><strong>{student.name}</strong> ({student.student_number or student.email}) has applied to join your project:</p>
        <div style="background:#f0f4ff;padding:15px;border-left:4px solid #003366;margin:15px 0;">
          <strong>{project.title}</strong>
        </div>
        {'<p><em>Message: ' + application.message + '</em></p>' if application.message else ''}
        <p>Please log in to review the application.</p>
      </div>
    </div>
    """
    send_email(f"New application for '{project.title}'", faculty.email, html)


def send_application_result(application):
    student = application.applicant
    project = application.project
    status = application.status.value
    color = '#2ecc71' if status == 'approved' else '#e74c3c'
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#003366;padding:25px;text-align:center;">
        <h2 style="color:white;margin:0;">Application Update</h2>
      </div>
      <div style="padding:25px;">
        <p>Hi <strong>{student.name}</strong>,</p>
        <p>Your application for <strong>{project.title}</strong> has been 
           <span style="color:{color};font-weight:bold;">{status.upper()}</span>.</p>
        {'<p>You can now view the project milestones and start collaborating!</p>' if status == 'approved' else ''}
      </div>
    </div>
    """
    send_email(f"Application {status} – {project.title}", student.email, html)


def send_milestone_deadline_reminder(user, milestone):
    project = milestone.project
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#e67e22;padding:25px;text-align:center;">
        <h2 style="color:white;margin:0;">⏰ Milestone Deadline Reminder</h2>
      </div>
      <div style="padding:25px;">
        <p>Hi <strong>{user.name}</strong>,</p>
        <p>The milestone <strong>{milestone.title}</strong> in project <strong>{project.title}</strong> 
           is due on <strong>{milestone.deadline.strftime('%d %B %Y')}</strong>.</p>
        <p>Please log in to check your progress.</p>
      </div>
    </div>
    """
    send_email(f"Reminder: '{milestone.title}' deadline approaching", user.email, html)


def send_feedback_notification(submission):
    student = submission.student
    task = submission.task
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#003366;padding:25px;text-align:center;">
        <h2 style="color:white;margin:0;">New Feedback Received</h2>
      </div>
      <div style="padding:25px;">
        <p>Hi <strong>{student.name}</strong>,</p>
        <p>Your faculty has reviewed your submission for task <strong>{task.title}</strong> 
           and left feedback. Log in to view it.</p>
      </div>
    </div>
    """
    send_email(f"Feedback on your submission: {task.title}", student.email, html)


def send_certificate_email(user, project, cert):
    html = f"""
    <div style="font-family:Georgia,serif;max-width:650px;margin:auto;border:3px double #002147;">
      <div style="background:linear-gradient(135deg,#002147,#003b6e);padding:30px;text-align:center;">
        <div style="font-size:2rem;color:#c8972c;font-weight:900;letter-spacing:2px;">DUT</div>
        <div style="color:rgba(255,255,255,.7);font-size:.75rem;letter-spacing:3px;text-transform:uppercase;">
          Durban University of Technology
        </div>
      </div>
      <div style="padding:40px;text-align:center;background:#fffdf7;">
        <div style="font-size:2.5rem;margin-bottom:10px;">🎓</div>
        <h2 style="color:#002147;font-size:1.6rem;margin:0 0 6px;">Certificate of Completion</h2>
        <p style="color:#888;font-size:.85rem;margin:0 0 30px;">This certifies that</p>
        <div style="font-size:1.8rem;font-weight:700;color:#002147;border-bottom:2px solid #c8972c;
             display:inline-block;padding-bottom:6px;margin-bottom:24px;">{user.name}</div>
        <p style="color:#555;margin:0 0 6px;">has successfully completed the project</p>
        <div style="font-size:1.2rem;font-weight:700;color:#003b6e;margin:12px 0;">{project.title}</div>
        <p style="color:#888;font-size:.85rem;">Faculty Supervisor: {project.faculty.name} &middot; {project.department or 'DUT'}</p>
        <div style="margin-top:30px;padding-top:20px;border-top:1px solid #eee;
             color:#aaa;font-size:.72rem;letter-spacing:.5px;">
          Certificate No: {cert.certificate_number} &middot; Issued: {cert.issued_at.strftime('%d %B %Y')}
        </div>
      </div>
    </div>
    """
    send_email(
        f"🎓 Certificate of Completion – {project.title}",
        user.email, html
    )


def send_badge_email(user, badge):
    meta = badge.meta
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#002147;padding:24px;text-align:center;">
        <h2 style="color:white;margin:0;">🏅 You Earned a Badge!</h2>
      </div>
      <div style="padding:28px;text-align:center;background:#f9f9f9;">
        <div style="width:80px;height:80px;background:{meta['color']};border-radius:50%;
             margin:0 auto 16px;display:flex;align-items:center;justify-content:center;font-size:2.2rem;">
          🏅
        </div>
        <h3 style="color:#002147;margin:0 0 8px;">{meta['label']}</h3>
        <p style="color:#666;margin:0 0 16px;">{meta['desc']}</p>
        <p>Congratulations <strong>{user.name}</strong>! Keep up the great work on the DUT Project Hub.</p>
      </div>
      <div style="padding:12px;background:#002147;text-align:center;color:rgba(255,255,255,.5);font-size:.72rem;">
        Durban University of Technology &middot; Faculty of Accounting &amp; Informatics
      </div>
    </div>
    """
    send_email(f"🏅 New Badge Earned: {meta['label']}", user.email, html)


def send_task_due_reminder_email(student, task, project):
    """Send a due-today reminder email to a student for an incomplete task."""
    due_str = task.due_date.strftime('%d %B %Y') if task.due_date else 'Today'
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:linear-gradient(135deg,#002147,#003b6e);
                  padding:28px;text-align:center;">
        <div style="font-size:2rem;">⏰</div>
        <h2 style="color:#fff;margin:8px 0 4px;">Task Due Today</h2>
        <p style="color:rgba(255,255,255,.65);margin:0;font-size:.85rem;">
          DUT Faculty–Student Project Hub
        </p>
      </div>

      <div style="padding:28px;background:#fffdf7;border-left:4px solid #f59e0b;">
        <p style="margin:0 0 12px;">Hi <strong>{student.name}</strong>,</p>
        <p style="margin:0 0 16px;color:#374151;">
          This is a reminder that the following task is due
          <strong style="color:#d97706;">today ({due_str})</strong>
          and has not yet been submitted:
        </p>

        <div style="background:#fff;border:1.5px solid #fcd34d;border-radius:8px;
                    padding:16px 20px;margin-bottom:20px;">
          <div style="font-size:1rem;font-weight:700;color:#002147;margin-bottom:4px;">
            {task.title}
          </div>
          <div style="color:#6b7280;font-size:.85rem;">
            Project: <strong>{project.title}</strong>
          </div>
          {f'<div style="color:#6b7280;font-size:.82rem;margin-top:4px;">{task.description}</div>' if task.description else ''}
        </div>

        <p style="color:#374151;margin:0 0 20px;">
          Please log in to the DUT Project Hub and submit your evidence file
          (PDF, DOC, DOCX, PPT, PPTX, PNG, JPG) before midnight tonight.
        </p>

        <div style="background:#fef3cd;border-radius:6px;padding:10px 14px;
                    font-size:.8rem;color:#92400e;margin-bottom:20px;">
          <strong>⚠ Note:</strong> You will continue to receive reminders every 4 hours
          until you submit your work or the day ends.
        </div>

        <a href="#"
           style="display:inline-block;background:#002147;color:#fff;
                  padding:12px 28px;border-radius:8px;text-decoration:none;
                  font-weight:600;font-size:.9rem;">
          Go to Project Hub
        </a>
      </div>

      <div style="padding:14px;background:#f3f4f6;text-align:center;
                  color:#9ca3af;font-size:.72rem;border-top:1px solid #e5e7eb;">
        Durban University of Technology · Faculty of Accounting &amp; Informatics<br>
        This is an automated reminder. Please do not reply to this email.
      </div>
    </div>
    """
    send_email(
        subject=f"⏰ Task Due Today: {task.title}",
        recipients=student.email,
        html_body=html
    )
