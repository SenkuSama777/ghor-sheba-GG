"""
Diagnostic helper — prints which database the app is currently configured
to use, and every registered user in it. Handy when make_admin.py says a
user "doesn't exist" even though you just registered and logged in with
that email: it usually means this script (or make_admin.py) is pointing at
a different database file than the running app is.

Usage:
    python list_users.py
"""
from app import create_app
from config import Config
from models import User

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print(f"Database in use: {Config.SQLALCHEMY_DATABASE_URI}\n")
        users = User.query.all()
        if not users:
            print("No users found in this database at all.")
            print("If you're sure you registered, the running app is almost")
            print("certainly using a different tripura_services.db file than")
            print("this script is — check you're in the same project folder")
            print("(no duplicate/nested copies) with the same venv active.")
        else:
            print(f"{len(users)} user(s):")
            for u in users:
                print(f"  - {u.email}  (role={u.role}, admin={u.is_admin})")
