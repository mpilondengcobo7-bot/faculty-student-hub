#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

export FLASK_APP=app:create_app

# Initialize migrations folder if it doesn't exist yet
if [ ! -d "migrations" ]; then
    flask db init
fi

# Generate migration from current models and apply
flask db migrate -m "auto migration" 2>/dev/null || true
flask db upgrade

# Seed default admin if none exists
python -c "
from app import create_app, db
from models import User, UserRole

flask_app = create_app()
with flask_app.app_context():
    if not User.query.filter_by(role=UserRole.ADMIN).first():
        admin = User(
            name='System Administrator',
            email='admin@dut.ac.za',
            role=UserRole.ADMIN,
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Default admin created.')
    else:
        print('Admin already exists.')
"
