# filepath: skillswap/rbac/__init__.py
"""SkillSwap — RBAC: Role-Based Access Control."""
from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def has_permission(user, perm_slug: str) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.id == 1: return True
    if user.is_admin and perm_slug != "can_manage_admins": return True
    try:
        for role in user.roles.all():
            if role.permissions.filter_by(slug=perm_slug).count():
                return True
    except Exception:
        pass
    return False


def require_permission(perm_slug: str):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if not has_permission(current_user, perm_slug): abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def get_highest_role(user) -> str:
    if user.id == 1: return "superadmin"
    try:
        roles = list(user.roles.order_by("priority").all())
        if roles: return roles[-1].slug
    except Exception:
        pass
    return "admin" if user.is_admin else "user"
