"""Portfolio data stays idempotent, realistic, and incapable of file operations."""
import re
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import inspect, text
from app import create_app
from app.demo import ACCOUNTS, ADMIN_HASH, USER_HASH, seed_demo
from app.extensions import db
from app.models import (
    ActivityLog, FileOperation, OrganizationRule, OrganizationSession,
    ScheduledTask, User, utcnow,
)
from app.scheduler import run_due
from app.schema import initialize_database


def credential(username):
    readme = (Path(__file__).resolve().parents[1] / 'README.md').read_text(encoding='utf-8')
    row = next(line for line in readme.splitlines() if line.startswith('|') and f'`{username}`' in line)
    return re.findall(r'`([^`]+)`', row)[2]


@pytest.fixture
def demo_app():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'demo-test-key',
                      'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        initialize_database()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def counts():
    return {model.__name__: model.query.count() for model in (
        User, OrganizationRule, OrganizationSession, FileOperation, ScheduledTask, ActivityLog,
    )}


def test_fresh_dataset_and_idempotence(demo_app):
    with demo_app.app_context():
        seed_demo()
        assert User.query.count() == 6
        assert OrganizationSession.query.count() == 24
        assert OrganizationRule.query.count() == 47
        assert ScheduledTask.query.count() == 18
        assert FileOperation.query.count() > 700
        assert ActivityLog.query.count() == 56
        assert OrganizationSession.query.filter_by(status='failed').count() == 1
        assert OrganizationSession.query.filter_by(status='partial').count() == 2
        for username, email, role in ACCOUNTS:
            user = User.query.filter_by(username=username).one()
            assert user.email == email and user.role == role and user.active
            assert user.check_password(credential(username))
            assert user.password_hash.startswith('scrypt:')
        for record in OrganizationSession.query.all():
            assert record.is_demo
            assert record.source_folder.startswith(('C:\\Users\\Demo\\', '/home/demo/'))
            assert record.files_scanned == len(record.files)
            if record.status != 'preview':
                assert record.files_scanned == record.files_moved + record.files_skipped + record.errors
            assert sum(op.status == 'moved' for op in record.files) == record.files_moved
        before = counts()
        seed_demo()
        assert counts() == before
        # Re-seeding must not reset account changes made after the initial seed.
        user = User.query.filter_by(username='alexjohnson').one()
        user.active = False
        user.set_password('ChangedPassword123!')
        changed_hash = user.password_hash
        db.session.commit()
        seed_demo()
        assert user.password_hash == changed_hash and not user.active


def test_demo_login_roles_and_readonly_preview(demo_app):
    with demo_app.app_context():
        seed_demo()
        preview_id = OrganizationSession.query.filter_by(status='preview').one().id
    client = demo_app.test_client()
    assert client.post('/auth/login', data={'identity': 'admin', 'password': credential('admin')}).status_code == 302
    assert client.get('/admin/').status_code == 200
    client.post('/auth/logout')
    assert client.post('/auth/login', data={'identity': 'alexjohnson', 'password': credential('alexjohnson')}).status_code == 302
    assert client.get('/dashboard').status_code == 200
    assert client.get('/admin/').status_code == 403
    response = client.post(f'/organize/sessions/{preview_id}/execute', data={'confirm': 'yes'}, follow_redirects=True)
    assert b'cannot be executed' in response.data
    assert client.post(f'/organize/sessions/{preview_id}/cancel').status_code == 400
    with demo_app.app_context():
        assert db.session.get(OrganizationSession, preview_id).status == 'preview'


def test_worker_ignores_even_active_due_demo_tasks(demo_app, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Demo task attempted a filesystem scan.')
    monkeypatch.setattr('app.scheduler.preview', forbidden)
    with demo_app.app_context():
        seed_demo()
        tasks = ScheduledTask.query.filter_by(is_active=True).all()
        assert len(tasks) == 12
        for task in tasks:
            task.next_run = utcnow() - timedelta(days=1)
        db.session.commit()
        before = [(task.id, task.last_run, task.next_run) for task in tasks]
        run_due()
        assert [(task.id, task.last_run, task.next_run) for task in tasks] == before


def test_existing_unrelated_identity_preserved(demo_app):
    with demo_app.app_context():
        user = User(username='admin', email='owner@example.com', role='admin', active=True)
        user.set_password('PrivatePassword123!')
        db.session.add(user)
        db.session.commit()
        previous_hash = user.password_hash
        summary = seed_demo()
        assert summary['skipped existing identities'] == 1
        assert user.email == 'owner@example.com' and user.password_hash == previous_hash
        assert User.query.filter_by(username='admin').count() == 1
        assert OrganizationSession.query.filter_by(user_id=user.id).count() == 0


def test_legacy_upgrade_preserves_real_history(demo_app):
    with demo_app.app_context():
        admin = User(username='admin', email='admin@example.com', role='admin', password_hash=ADMIN_HASH)
        legacy = User(username='alex', email='alex@example.com', role='user', password_hash=USER_HASH)
        db.session.add_all([admin, legacy])
        db.session.flush()
        for user in (admin, legacy):
            db.session.add(ActivityLog(user_id=user.id, action='Demo seeded', details='Legacy seed.'))
        real = OrganizationSession(user_id=admin.id, source_folder='/approved/real-folder', is_demo=False, status='completed')
        synthetic = OrganizationSession(user_id=legacy.id, source_folder='/old/machine/folder', is_demo=True, status='completed')
        db.session.add_all([real, synthetic])
        db.session.flush()
        db.session.add(FileOperation(session_id=synthetic.id, original_path='/old/machine/folder/report.pdf',
                                    destination_path='/old/machine/folder/Documents/report.pdf', filename='report.pdf', status='moved'))
        db.session.commit()
        real_id = real.id
        seed_demo()
        assert legacy.username == 'alexjohnson'
        assert db.session.get(OrganizationSession, real_id).source_folder == '/approved/real-folder'
        assert synthetic.source_folder.startswith(('C:\\Users\\Demo\\', '/home/demo/'))
        assert '/old/machine' not in synthetic.files[0].destination_path


def test_schema_upgrade_is_additive_and_idempotent(demo_app):
    with demo_app.app_context():
        with db.engine.begin() as connection:
            connection.execute(text('DROP TABLE scheduled_task'))
            connection.execute(text('CREATE TABLE scheduled_task (id INTEGER PRIMARY KEY, folder_path TEXT)'))
            connection.execute(text("INSERT INTO scheduled_task (id, folder_path) VALUES (1, '/approved/existing')"))
        initialize_database()
        initialize_database()
        columns = {column['name'] for column in inspect(db.engine).get_columns('scheduled_task')}
        assert {'name', 'is_demo'} <= columns
        with db.engine.connect() as connection:
            row = connection.execute(text('SELECT folder_path, name, is_demo FROM scheduled_task')).one()
            assert row == ('/approved/existing', 'Organization routine', 0)


def test_production_seed_rejected(demo_app):
    demo_app.config['SESSION_COOKIE_SECURE'] = True
    with demo_app.app_context(), pytest.raises(RuntimeError, match='production'):
        seed_demo()
