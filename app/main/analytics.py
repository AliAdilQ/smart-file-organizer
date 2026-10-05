from collections import Counter
from app.models import OrganizationSession, FileOperation


def analytics(user_id=None):
    sessions = OrganizationSession.query
    files = FileOperation.query.join(OrganizationSession)
    if user_id is not None:
        sessions = sessions.filter(OrganizationSession.user_id == user_id)
        files = files.filter(OrganizationSession.user_id == user_id)
    moved = files.filter(FileOperation.status.in_(['moved', 'undone', 'undo_error'])).all()
    records = sessions.order_by(OrganizationSession.started_at.desc()).all()
    categories = Counter(op.category for op in moved)
    extensions = Counter(op.extension or '(none)' for op in moved)
    dates = Counter(op.session.started_at.strftime('%Y-%m-%d') for op in moved)
    return {
        'total': len(moved), 'storage': sum(op.file_size for op in moved),
        'sessions': sum(s.status not in ('preview', 'cancelled') for s in records),
        'common': categories.most_common(1)[0][0] if categories else '—',
        'extension': extensions.most_common(1)[0][0] if extensions else '—',
        'last': next((s.started_at for s in records if s.files_moved), None),
        'success': sum(s.status in ('completed', 'undone') for s in records),
        'failed': sum(s.status in ('failed', 'partial', 'undo_partial') for s in records),
        'category_labels': list(categories), 'category_values': list(categories.values()),
        'extension_labels': [x[0] for x in extensions.most_common(8)],
        'extension_values': [x[1] for x in extensions.most_common(8)],
        'date_labels': sorted(dates), 'date_values': [dates[d] for d in sorted(dates)],
        'recent': records[:6],
    }
