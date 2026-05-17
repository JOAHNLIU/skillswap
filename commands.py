# filepath: commands.py
# SkillSwap - Flask CLI Commands
# Windows: set FLASK_APP=app:create_app && flask make-admin email@example.com
# Mac/Linux: export FLASK_APP=app:create_app && flask make-admin email@example.com

import click
from flask import Blueprint

cli_bp = Blueprint("cli", __name__, cli_group=None)


@cli_bp.cli.command("make-admin")
@click.argument("email")
def make_admin(email):
    """Grant admin rights. Usage: flask make-admin user@example.com"""
    from extensions import db
    from models import User
    user = User.query.filter_by(email=email.lower().strip()).first()
    if not user:
        click.secho(f"ERROR: User '{email}' not found.", fg="red")
        return
    if user.is_admin:
        click.secho(f"INFO: {email} is already admin.", fg="yellow")
        return
    user.is_admin = True
    db.session.commit()
    click.secho(f"OK: Admin rights granted to {email}", fg="green")


@cli_bp.cli.command("revoke-admin")
@click.argument("email")
def revoke_admin(email):
    """Revoke admin rights. Usage: flask revoke-admin user@example.com"""
    from extensions import db
    from models import User
    user = User.query.filter_by(email=email.lower().strip()).first()
    if not user:
        click.secho(f"ERROR: User '{email}' not found.", fg="red")
        return
    if not user.is_admin:
        click.secho(f"INFO: {email} is not admin.", fg="yellow")
        return
    user.is_admin = False
    db.session.commit()
    click.secho(f"OK: Admin rights revoked from {email}", fg="green")


@cli_bp.cli.command("list-admins")
def list_admins():
    """Show all admins. Usage: flask list-admins"""
    from models import User
    admins = User.query.filter_by(is_admin=True).all()
    if not admins:
        click.secho("No admins found.", fg="yellow")
        return
    click.secho(f"\n{'ID':<6} {'Email':<35} {'Name':<25}", fg="cyan", bold=True)
    click.secho("-" * 66, fg="cyan")
    for u in admins:
        marker = " (superadmin)" if u.id == 1 else ""
        click.echo(f"{u.id:<6} {u.email:<35} {(u.full_name or ''):<25}{marker}")
    click.echo()


@cli_bp.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
def create_admin(email, password):
    """Create new admin. Usage: flask create-admin admin@test.com MyPass123"""
    from extensions import db
    from models import User
    existing = User.query.filter_by(email=email.lower()).first()
    if existing:
        existing.is_admin = True
        db.session.commit()
        click.secho(f"OK: Existing user {email} granted admin.", fg="green")
        return
    u = User(email=email.lower(), full_name="Admin",
             is_admin=True, onboarding_done=True, email_verified=True)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    click.secho(f"OK: Admin created: {email}", fg="green")
