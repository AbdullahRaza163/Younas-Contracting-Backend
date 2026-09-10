# reset_admin.py
from app import app
from models import db, User

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    
    if admin:
        print(f"Found admin: {admin.username}")
        admin.set_password('Admin@123')
        db.session.commit()
        print("✅ Password reset to: Admin@123")
        print(f"Verification: {admin.check_password('Admin@123')}")
    else:
        print("Admin not found. Creating new admin...")
        admin = User(
            id='admin123',
            username='admin',
            email='admin@hajiyounas.com',
            full_name='System Administrator',
            role='admin'
        )
        admin.set_password('Admin@123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created with password: Admin@123")