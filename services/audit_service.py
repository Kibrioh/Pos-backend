from models import AuditLog


def add_audit_event(actor_user_id, action, entity_type, entity_id=None, details=None):
    """Add an audit event to the current transaction."""
    from extensions import db

    db.session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )
