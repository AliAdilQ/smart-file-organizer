from datetime import datetime, timedelta
from app.scheduler import next_occurrence, run_due
from app.models import ScheduledTask, utcnow, OrganizationSession
from app.extensions import db


def test_monthly_calendar():
    assert next_occurrence(datetime(2024, 1, 31), 'monthly') == datetime(2024, 2, 29)
    assert next_occurrence(datetime(2025, 12, 31), 'monthly') == datetime(2026, 1, 31)


def test_due_task(app, folder):
    (folder / 'a.txt').write_text('scheduled')
    with app.app_context():
        task = ScheduledTask(user_id=1, folder_path=str(folder), frequency='daily', mode='type', next_run=utcnow() - timedelta(minutes=1))
        db.session.add(task)
        db.session.commit()
        run_due()
        assert task.last_run is not None
        assert task.next_run > utcnow()
        assert (folder / 'Documents' / 'a.txt').read_text() == 'scheduled'
        assert OrganizationSession.query.count() == 1
        run_due()
        assert OrganizationSession.query.count() == 1


def test_schedule_requires_consent(client, login, folder, app):
    login()
    client.post('/schedules', data={'folder': str(folder), 'mode': 'type', 'frequency': 'daily', 'rule_id': '0'})
    with app.app_context():
        assert ScheduledTask.query.count() == 0
