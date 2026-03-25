from app import db
from models import Notification


def create_notification(user_id, title, message, notif_type='info', link=None):
    """Create an in-app notification."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notif_type=notif_type,
        link=link
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def notify_application_received(application):
    create_notification(
        user_id=application.project.faculty_id,
        title="New Application",
        message=f"{application.applicant.name} applied to '{application.project.title}'",
        notif_type="info",
        link=f"/projects/{application.project_id}/applications"
    )


def notify_application_result(application):
    status = application.status.value
    notif_type = 'success' if status == 'approved' else 'warning'
    create_notification(
        user_id=application.student_id,
        title=f"Application {status.capitalize()}",
        message=f"Your application for '{application.project.title}' was {status}.",
        notif_type=notif_type,
        link=f"/projects/{application.project_id}"
    )


def notify_milestone_created(project, milestone):
    for participant in project.participants:
        create_notification(
            user_id=participant.id,
            title="New Milestone Added",
            message=f"New milestone '{milestone.title}' added to '{project.title}'",
            notif_type="info",
            link=f"/projects/{project.id}"
        )


def notify_milestone_completed(milestone):
    project = milestone.project
    create_notification(
        user_id=project.faculty_id,
        title="Milestone Completed",
        message=f"Milestone '{milestone.title}' in '{project.title}' marked as completed.",
        notif_type="success",
        link=f"/projects/{project.id}"
    )


def notify_feedback_given(submission):
    create_notification(
        user_id=submission.student_id,
        title="Feedback Received",
        message=f"Your faculty reviewed your submission for '{submission.task.title}'",
        notif_type="info",
        link=f"/projects/{submission.task.project_id}"
    )


def notify_new_project(project, users):
    """Notify all students about a new project."""
    for user in users:
        if user.id != project.faculty_id:
            create_notification(
                user_id=user.id,
                title="New Project Posted",
                message=f"'{project.title}' is now open for applications.",
                notif_type="info",
                link=f"/projects/{project.id}"
            )
