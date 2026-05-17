# filepath: skillswap/audit/__init__.py
"""SkillSwap — Audit Trail: append-only log of significant system actions."""

def log_action(action: str, target_type: str = "",
               target_id: int = None, old_value: str = "",
               new_value: str = "", actor_id: int = None) -> None:
    """Record audit entry. Never raises — silently skips on error."""
    try:
        from extensions import db
        from models import AuditLog
        from flask_login import current_user
        from flask import request
        aid = actor_id
        if aid is None:
            try:
                aid = current_user.id if current_user.is_authenticated else None
            except Exception:
                pass
        ip, ua = "", ""
        try:
            ip = (request.environ.get("HTTP_X_FORWARDED_FOR") or request.remote_addr or "")[:45]
            ua = (request.user_agent.string or "")[:200]
        except Exception:
            pass
        db.session.add(AuditLog(
            actor_id=aid, action=action,
            target_type=target_type, target_id=target_id,
            old_value=str(old_value)[:500], new_value=str(new_value)[:500],
            ip_address=ip, user_agent=ua,
        ))
    except Exception:
        pass
