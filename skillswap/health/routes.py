# filepath: skillswap/health/routes.py
"""SkillSwap — Platform Health Dashboard."""

import os, time, json
from datetime import datetime, timezone, timedelta
from flask import jsonify, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from skillswap.health import health_bp


def _admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def w(*a, **kw):
        if not current_user.is_admin: abort(403)
        return f(*a, **kw)
    return w


def _db_health():
    try:
        t = time.perf_counter()
        from models import User, Skill, Exchange, AuditLog
        counts = {"users": User.query.count(), "skills": Skill.query.count(),
                  "exchanges": Exchange.query.count(), "audit_log": AuditLog.query.count()}
        return {"status": "ok", "latency_ms": round((time.perf_counter()-t)*1000,1), "counts": counts}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _sys_health():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
        return {"status": "ok" if cpu < 85 and ram.percent < 85 else "warning",
                "cpu_percent": cpu, "ram_percent": ram.percent,
                "ram_free_mb": round(ram.available/1024**2, 1),
                "uptime_hours": round((datetime.now(timezone.utc)-boot).total_seconds()/3600, 1)}
    except ImportError:
        return {"status": "not_configured", "note": "psutil not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _disk_health():
    try:
        import psutil
        upload_path = os.path.abspath(os.environ.get("UPLOAD_FOLDER",
                                      "skillswap/static/uploads/avatars"))
        base = upload_path if os.path.exists(upload_path) else "."
        disk = psutil.disk_usage(base)
        fc, fsize = 0, 0
        if os.path.exists(upload_path):
            for f in os.scandir(upload_path):
                if f.is_file(): fc += 1; fsize += f.stat().st_size // 1024
        return {"status": "ok" if disk.percent < 90 else "warning",
                "disk_percent_used": disk.percent,
                "disk_free_gb": round(disk.free/1024**3, 2),
                "uploads_count": fc, "uploads_size_kb": fsize}
    except ImportError:
        return {"status": "not_configured", "note": "psutil not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _celery_health():
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        return {"status": "not_configured", "note": "Set REDIS_URL in .env"}
    try:
        import redis as rl
        r = rl.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        info = r.info("server")
        return {"status": "ok", "redis_version": info.get("redis_version","?"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "?")}
    except ImportError:
        return {"status": "not_configured", "note": "redis package not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _kpi_health():
    try:
        from models import User, Exchange, Review, Dispute, Session as Sess
        now = datetime.now(timezone.utc)
        day, week = now - timedelta(hours=24), now - timedelta(days=7)
        return {
            "status": "ok",
            "registrations_24h": User.query.filter(User.created_at >= day).count(),
            "registrations_7d":  User.query.filter(User.created_at >= week).count(),
            "exchanges_24h":     Exchange.query.filter(Exchange.created_at >= day).count(),
            "completed_24h":     Exchange.query.filter(Exchange.updated_at >= day,
                                                        Exchange.status=="completed").count(),
            "reviews_24h":       Review.query.filter(Review.created_at >= day).count(),
            "disputes_open":     Dispute.query.filter(
                                     Dispute.status.in_(["open","under_review"])).count(),
            "sessions_missed_7d":Sess.query.filter(
                                     Sess.status=="missed",
                                     Sess.scheduled_at >= week).count(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _error_health():
    try:
        from models import AuditLog, Dispute
        h1 = datetime.now(timezone.utc) - timedelta(hours=1)
        h24 = datetime.now(timezone.utc) - timedelta(hours=24)
        errors = AuditLog.query.filter(AuditLog.action.like("%error%"),
                                        AuditLog.created_at >= h1).count()
        disputes = AuditLog.query.filter(AuditLog.action == "dispute_opened",
                                          AuditLog.created_at >= h24).count()
        return {"status": "warning" if errors > 10 else "ok",
                "errors_last_1h": errors, "disputes_24h": disputes}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _collect():
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "db": _db_health(), "system": _sys_health(),
        "disk": _disk_health(), "celery": _celery_health(),
        "kpi": _kpi_health(), "errors": _error_health(),
    }


def _overall(data):
    statuses = [v.get("status","ok") for v in data.values() if isinstance(v,dict)]
    if "error" in statuses: return "error"
    if "warning" in statuses: return "warning"
    return "ok"


@health_bp.route("/")
@_admin_required
def dashboard():
    data = _collect()
    return render_template("health/dashboard.html", title="Health Dashboard",
                           data=data, overall=_overall(data),
                           json_data=json.dumps(data, ensure_ascii=False, indent=2))


@health_bp.route("/status")
def status():
    """Public JSON health check for uptime monitors."""
    db_h = _db_health()
    overall = "error" if db_h.get("status") == "error" else "ok"
    return jsonify({"status": overall,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "db": db_h.get("status"),
                    "db_latency_ms": db_h.get("latency_ms"),
                    "version": "1.0.0"}), 200 if overall == "ok" else 503


@health_bp.route("/metrics")
@_admin_required
def metrics():
    data = _collect()
    data["overall"] = _overall(data)
    return jsonify(data)


@health_bp.route("/snapshot", methods=["POST"])
@_admin_required
def snapshot():
    try:
        from models import PlatformMetric
        kpi = _kpi_health(); sys = _sys_health()
        now = datetime.now(timezone.utc)
        rows = [
            PlatformMetric(metric="registrations_24h", value=kpi.get("registrations_24h",0), recorded_at=now),
            PlatformMetric(metric="exchanges_24h",     value=kpi.get("exchanges_24h",0),     recorded_at=now),
            PlatformMetric(metric="completed_24h",     value=kpi.get("completed_24h",0),     recorded_at=now),
            PlatformMetric(metric="disputes_open",     value=kpi.get("disputes_open",0),     recorded_at=now),
            PlatformMetric(metric="cpu_percent",       value=sys.get("cpu_percent",0),       recorded_at=now),
            PlatformMetric(metric="ram_percent",       value=sys.get("ram_percent",0),       recorded_at=now),
        ]
        db.session.add_all(rows)
        db.session.commit()
        flash(f"✅ Snapshot збережено ({len(rows)} метрик).", "success")
    except Exception as e:
        flash(f"❌ Помилка: {e}", "danger")
    return redirect(url_for("health.dashboard"))
