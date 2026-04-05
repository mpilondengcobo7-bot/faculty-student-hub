# DUT Faculty–Student Collaborative Project Hub
**Group 14 – THE FOLKS | Faculty of Accounting & Informatics, DUT**

---

## Overview
A web-based platform that centralises academic project collaboration between faculty and students at Durban University of Technology. Faculty post projects, manage milestones, and review student submissions. Students discover, apply, and track their progress.

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.0 |
| ORM | Flask-SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| Auth | Flask-Login, Authlib (Microsoft OAuth/Azure AD) |
| Email | Flask-Mail (Office 365 SMTP) |
| Frontend | Bootstrap 5.3, Bootstrap Icons, custom CSS/JS |
| Migrations | Flask-Migrate (Alembic) |

---

## Project Structure
```
hub/
├── app.py                  # App factory & extension init
├── config.py               # Configuration
├── models.py               # SQLAlchemy models
├── run.py                  # Entry point
├── requirements.txt
├── .env.example            # Environment template
├── blueprints/
│   ├── auth.py             # Login, register, Microsoft OAuth, profile
│   ├── main.py             # Dashboards (faculty / student / admin)
│   ├── projects.py         # Project CRUD + applications
│   ├── milestones.py       # Milestones, tasks, submissions, feedback
│   ├── notifications.py    # In-app notification API + list
│   └── admin.py            # User & project management
├── services/
│   ├── email_service.py    # Email notifications (welcome, applications, feedback, deadlines)
│   └── notification_service.py  # In-app notification helpers
├── templates/
│   ├── base.html
│   ├── auth/               # login, register, profile
│   ├── main/               # faculty_dashboard, student_dashboard, admin_dashboard, index
│   ├── projects/           # list, detail, create, edit, applications
│   ├── milestones/         # create, edit, create_task
│   ├── notifications/      # list
│   └── admin/              # users, projects
└── static/
    ├── css/main.css
    └── js/main.js
```

---

## Setup & Run

### 1. Clone and install dependencies
```bash
git clone <repo>
cd hub
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Run (creates DB and default admin)
```bash
python run.py
```
Open http://localhost:5000

**Default Admin:** `admin@dut.ac.za` / `admin123` *(change immediately)*

---

## Microsoft OAuth Setup (Azure AD)
1. Go to [Azure Portal](https://portal.azure.com) → **Azure Active Directory** → **App Registrations** → **New Registration**
2. Name: `DUT Project Hub`
3. Redirect URI: `http://localhost:5000/auth/microsoft/callback` (add production URL when deploying)
4. Under **Certificates & secrets**, create a new client secret
5. Copy **Application (client) ID**, **Client Secret**, and your **Directory (tenant) ID** into `.env`
6. For institutional-only login, set `MICROSOFT_TENANT_ID` to your DUT tenant ID

---

## Role-Based Access Control
| Feature | Student | Faculty | Admin |
|---|---|---|---|
| Browse projects | ✅ | ✅ | ✅ |
| Apply to project | ✅ | ❌ | ❌ |
| Post project | ❌ | ✅ | ❌ |
| Edit own project | ❌ | ✅ | ✅ |
| Create milestones | ❌ | ✅ | ✅ |
| Complete milestone | ❌ | ✅ | ✅ |
| Mark milestone in-progress | ✅ | ✅ | ✅ |
| Submit task | ✅ | ❌ | ❌ |
| Give feedback | ❌ | ✅ | ❌ |
| Review applications | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ✅ |

---

## Email Notifications
- Welcome email on registration
- Faculty notified when a student applies
- Student notified on application approval/rejection
- Faculty notified when a milestone is completed
- Students notified when new milestones are added
- Students notified when feedback is given on submissions

---

## Production Deployment
- Set `DEBUG=False` in config
- Use PostgreSQL: `DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname`
- Run migrations: `flask db upgrade`
- Use Gunicorn: `gunicorn -w 4 "app:create_app()"`
- Set a strong `SECRET_KEY`
