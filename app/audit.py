from flask import current_app, has_request_context, request
from app.extensions import db
from app.models import ActivityLog


def audit(user_id, action, details=''):
    db.session.add(ActivityLog(user_id=user_id, action=action, details=details,
                              ip_address=request.remote_addr if has_request_context() else None))
    current_app.logger.info('%s user=%s %s', action, user_id, details)
