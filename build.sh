#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python -c "
from app import create_app, db
from models import User, UserRole

flask_app = create_app()
with flask_app.app_context():
    db.create_all()
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
