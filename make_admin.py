#!/usr/bin/env python3
"""
SkillSwap — Quick admin grant script for Windows users.

Usage (from project folder with venv activated):
  python make_admin.py your@email.com
"""
import sys
import os

if len(sys.argv) < 2:
    print("Usage: python make_admin.py your@email.com")
    sys.exit(1)

email = sys.argv[1].lower().strip()

# Must run from project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from models import User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email=email).first()
    if not user:
        print(f"❌  User '{email}' not found. Register first at http://127.0.0.1:5000/auth/register")
        sys.exit(1)
    if user.is_admin:
        print(f"ℹ️   {email} is already an admin.")
        sys.exit(0)
    user.is_admin = True
    db.session.commit()
    print(f"✅  Admin rights granted to: {email}")
