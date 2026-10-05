"""One dedicated worker, never a thread started by the Flask reloader."""
import calendar
from datetime import timedelta
from app.extensions import db
from app.models import ScheduledTask, utcnow
from app.organizer.services import preview, execute
from app.audit import audit


def next_occurrence(date, frequency):
    if frequency == 'daily':
        return date + timedelta(days=1)
    if frequency == 'weekly':
        return date + timedelta(days=7)
    if frequency != 'monthly':
        raise ValueError('Unknown schedule frequency.')
    month = date.month % 12 + 1
    year = date.year + (date.month == 12)
    return date.replace(year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1]))


def run_due():
    now = utcnow()
    for task in ScheduledTask.query.filter(ScheduledTask.is_active.is_(True),
                                          ScheduledTask.is_demo.is_(False), ScheduledTask.next_run <= now).all():
        if not task.user.active:
            task.is_active = False
            db.session.commit()
            continue
        # Claim the occurrence before I/O. No repeated job after a worker crash.
        old_run = task.next_run
        claimed = ScheduledTask.query.filter_by(id=task.id, next_run=old_run, is_active=True).update(
            {'next_run': next_occurrence(now, task.frequency), 'last_run': now})
        db.session.commit()
        if not claimed:
            continue
        try:
            record = preview(task.user_id, task.folder_path, task.mode, task.rule_id)
            execute(record)
            task.last_error = f'{record.errors} file errors; see session {record.id}' if record.errors else None
        except (ValueError, OSError) as error:
            task.last_error = str(error)
            audit(task.user_id, 'Schedule failed', f'Task {task.id}: {error}')
        db.session.commit()
