"""
Promote an existing user to admin so they can verify providers.

Usage:
    python make_admin.py someone@example.com
"""
import sys

from app import create_app
from models import db, User

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"No user found with email {email}")
            sys.exit(1)
        user.is_admin = True
        db.session.commit()
        print(f"{email} is now an admin.")
