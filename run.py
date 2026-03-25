from app import create_app, db

flask_app = create_app()

if __name__ == '__main__':
    with flask_app.app_context():
        db.create_all()
        # Create default admin if none exists
        from models import User, UserRole
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
            print("Default admin created: admin@dut.ac.za / admin123")
    flask_app.run(debug=True, host='0.0.0.0', port=4500)
