import sys
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import get_settings
from app.database import SessionLocal, engine
from app.models.base import Organization, User, Membership
from app.core.password_utils import hash_password

settings = get_settings()

def seed_demo_accounts():
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(User).filter(User.email.like('%@demo.example')).count()
        if existing > 0:
            print(f'Skip: {existing} demo accounts already exist')
            return

        # Create organization
        org = Organization(
            name='دانشگاه آزمایشی نوین',
            slug='novin-university',
            timezone='Asia/Tehran'
        )
        db.add(org)
        db.flush()
        org_id = org.id
        print(f'Organization created: id={org_id}')

        # Create test accounts
        accounts = [
            ('admin@demo.example', 'مدیر کل آزمایشی', 'admin', True),
            ('employee01@demo.example', 'کارمند شماره ۱', 'unit_manager', True),
            ('employee02@demo.example', 'کارمند شماره ۲', 'unit_manager', True),
            ('employee03@demo.example', 'کارمند شماره ۳', 'unit_manager', True),
            ('employee04@demo.example', 'کارمند شماره ۴', 'unit_manager', True),
            ('employee05@demo.example', 'کارمند شماره ۵', 'unit_manager', True),
        ]

        for email, name, role, must_change in accounts:
            user = User(
                email=email,
                password_hash=hash_password('12345678'),
                full_name=name,
                must_change_password=must_change,
                is_active=True,
                organization_id=org_id
            )
            db.add(user)
            db.flush()

            membership = Membership(
                user_id=user.id,
                organization_id=org_id,
                role=role
            )
            db.add(membership)
            print(f'Created: {email} ({role}, must_change={must_change})')

        db.commit()
        print('All test accounts seeded successfully')
    finally:
        db.close()

if __name__ == '__main__':
    seed_demo_accounts()
