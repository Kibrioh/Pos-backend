from flask import Blueprint, jsonify, request

from models import AuditLog
from utils.auth import manager_required

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
@manager_required
def list_audit_events():
    limit = request.args.get("limit", default=100, type=int)
    limit = min(max(limit or 100, 1), 500)
    events = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify([event.to_dict() for event in events]), 200
