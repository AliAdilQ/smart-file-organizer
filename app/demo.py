"""Repeatable, fictional portfolio data, separate from real filesystem actions."""
from datetime import timedelta
from pathlib import PurePosixPath, PureWindowsPath
import re
from flask import current_app
from app.extensions import db
from app.models import (
    ActivityLog, FileOperation, OrganizationRule, OrganizationSession,
    ScheduledTask, User, utcnow,
)
from app.organizer.rules import seed_defaults
from app.schema import initialize_database

# Generated with User.set_password (Werkzeug scrypt). Cleartext credentials are
# documented only in README's Demo Credentials section, never in logs or output.
ADMIN_HASH = (
    'scrypt:32768:8:1$cEH8JJsaDSnmuFUH$'
    '252d862a0e502321f59de117bb0968cb412b4827feb97ca813ba235117bd7e3b3'
    'ede92cc601a78bd28277c2761958ee52dd952962413f5b04b6fd1a17e577f56'
)
USER_HASH = (
    'scrypt:32768:8:1$RZNDcohItFVuspCz$'
    'bd94e46c0acb3d7f3a45d1e28248426f401e7f90bded336b0013d5e9ff1cbacf'
    'a6b43d5c014ec4c4207cd2030ab8b9321d280de2f523b1360baa1869dfed3828'
)
ACCOUNTS = (
    ('admin', 'admin@example.com', 'admin'),
    ('alexjohnson', 'alex@example.com', 'user'),
    ('sarahmiller', 'sarah@example.com', 'user'),
    ('davidlee', 'david@example.com', 'user'),
    ('emmawilson', 'emma@example.com', 'user'),
    ('michaelbrown', 'michael@example.com', 'user'),
)
FOLDERS = (
    r'C:\Users\Demo\Downloads', r'C:\Users\Demo\Desktop',
    r'C:\Users\Demo\Documents', '/home/demo/Downloads', '/home/demo/Desktop',
)
RULES = (
    ('Documents', '.pdf .doc .docx .txt', 'Documents', 1),
    ('Images', '.jpg .jpeg .png .gif .webp', 'Images', 2),
    ('Videos', '.mp4 .mkv .avi .mov', 'Videos', 3),
    ('Archives', '.zip .rar .7z', 'Archives', 4),
    ('Python Projects', '.py .ipynb', 'Programming/Python', 5),
    ('University Files', '.pdf .pptx .docx', 'University', 6),
)
FILES = (
    ('resume.pdf', 'Documents', 184_320),
    ('assignment.docx', 'Documents', 872_448),
    ('budget.xlsx', 'Spreadsheets', 245_760),
    ('presentation.pptx', 'University Files', 5_812_224),
    ('vacation.jpg', 'Images', 3_145_728),
    ('profile.png', 'Images', 1_572_864),
    ('tutorial.mp4', 'Videos', 157_286_400),
    ('podcast.mp3', 'Audio', 42_991_616),
    ('backup.zip', 'Archives', 83_886_080),
    ('script.py', 'Python Projects', 8_192),
    ('analysis.ipynb', 'Python Projects', 91_136),
    ('notes.txt', 'Documents', 4_096),
    ('report.pdf', 'Documents', 2_097_152),
    ('invoice.pdf', 'Documents', 307_200),
    ('project.zip', 'Archives', 26_214_400),
)
MARKER = 'Demo dataset v2'
LEGACY_MARKER = 'Demo seeded'


def demo_path(folder, *parts):
    """Format fictional paths independently of the host OS."""
    path = PureWindowsPath(folder) if folder.startswith('C:') else PurePosixPath(folder)
    return str(path.joinpath(*parts))


def _has_marker(user_id, action):
    return ActivityLog.query.filter_by(user_id=user_id, action=action).first() is not None


def _upgrade_legacy_accounts():
    """Rename only untouched, positively identified v1 seeded regular accounts."""
    aliases = (
        ('alex', 'alex@example.com', ACCOUNTS[1]),
        ('maya', 'maya@example.com', ACCOUNTS[2]),
        ('jordan', 'jordan@example.com', ACCOUNTS[3]),
        ('sam', 'sam@example.com', ACCOUNTS[4]),
    )
    for old_name, old_email, (name, email, _) in aliases:
        user = User.query.filter_by(username=old_name, email=old_email).first()
        if not user or not _has_marker(user.id, LEGACY_MARKER):
            continue
        conflict = User.query.filter(
            User.id != user.id, (User.username == name) | (User.email == email)
        ).first()
        real_history = OrganizationSession.query.filter_by(user_id=user.id, is_demo=False).first()
        authored_events = ActivityLog.query.filter(
            ActivityLog.user_id == user.id,
            ActivityLog.action.notin_([LEGACY_MARKER, 'Login', 'Logout']),
        ).first()
        if conflict or real_history or authored_events or user.role != 'user' or not user.active:
            continue
        user.username, user.email, user.password_hash = name, email, USER_HASH
        db.session.add(ActivityLog(
            user_id=user.id, action='Legacy demo account upgraded',
            details='Untouched synthetic account migrated to the portfolio dataset.',
        ))
    db.session.flush()


def _normalize_legacy_paths():
    """Remove machine-specific locations from illustrative v1 records only."""
    old_sources = {}
    for record in OrganizationSession.query.filter_by(is_demo=True).all():
        if record.source_folder.replace('\\', '/').startswith(('C:/Users/Demo/', '/home/demo/')):
            continue
        old_sources.setdefault(record.user_id, set()).add(record.source_folder)
        previous = record.source_folder.replace('\\', '/').rstrip('/') + '/'
        folder = FOLDERS[record.id % len(FOLDERS)]
        for operation in record.files:
            target = operation.destination_path.replace('\\', '/')
            relative = target[len(previous):] if target.startswith(previous) else operation.filename
            operation.original_path = demo_path(folder, operation.filename)
            operation.destination_path = demo_path(folder, *relative.split('/'))
        record.source_folder = folder
    for user_id, sources in old_sources.items():
        if not _has_marker(user_id, LEGACY_MARKER):
            continue
        for task in ScheduledTask.query.filter_by(user_id=user_id, is_active=False, last_run=None).all():
            if task.folder_path in sources and task.frequency == 'weekly' and task.rule_id is None:
                task.folder_path = FOLDERS[1]
                task.name, task.is_demo = 'Desktop Weekly Cleanup', True


def _seed_rules(user, now):
    for name, extensions, destination, priority in RULES:
        if not OrganizationRule.query.filter_by(user_id=user.id, name=name).first():
            db.session.add(OrganizationRule(
                user_id=user.id, name=name, extensions=extensions,
                destination=destination, priority=priority, is_active=True,
                created_at=now - timedelta(days=35 - priority),
            ))


def _retire_legacy_fixtures():
    """Replace positively identified v1 illustrations, never real sessions."""
    pattern = re.compile(r'^(report|photo|clip|budget|backup|notes|project)_\d+_\d+\.[a-z0-9]+$')
    legacy_ids = {log.user_id for log in ActivityLog.query.filter_by(action=LEGACY_MARKER).all()}
    for record in OrganizationSession.query.filter_by(
        is_demo=True, mode='type', status='completed', files_scanned=14,
        files_moved=14, files_skipped=0, errors=0,
    ).all():
        if (record.user_id in legacy_ids and len(record.files) == 14
                and all(pattern.fullmatch(operation.filename) for operation in record.files)):
            db.session.delete(record)
    for task in ScheduledTask.query.filter_by(
        is_demo=True, is_active=False, last_run=None, name='Desktop Weekly Cleanup',
    ).all():
        if task.user_id in legacy_ids:
            db.session.delete(task)
    for rule in OrganizationRule.query.filter_by(
        name='University documents', extensions='.pdf .docx',
        destination='University/Notes', priority=50,
    ).all():
        if rule.user_id in legacy_ids and not ScheduledTask.query.filter_by(rule_id=rule.id).first():
            db.session.delete(rule)


def _seed_sessions(user, account_index, now):
    for slot in range(4):
        index = account_index * 4 + slot
        folder = FOLDERS[(account_index + slot) % len(FOLDERS)]
        started = (now - timedelta(days=slot * 6 + account_index, hours=slot * 2))
        is_preview = account_index == 1 and slot == 0
        if is_preview:
            folder, started = FOLDERS[0], now
        outcome = 'preview' if is_preview else (
            'failed' if index == 15 else 'partial' if index in (9, 20) else 'completed'
        )
        scanned = 12 if is_preview else 24 + ((index * 7) % 29)
        skipped = 0 if is_preview else 2 + index % 5
        errors = scanned - skipped if outcome == 'failed' else 2 if outcome == 'partial' else 0
        moved = 0 if outcome in ('preview', 'failed') else scanned - skipped - errors
        record = OrganizationSession(
            user_id=user.id, source_folder=folder, mode=('type', 'month', 'extension', 'size')[slot],
            started_at=started, completed_at=None if is_preview else started + timedelta(seconds=18 + index * 3),
            files_scanned=scanned, files_moved=moved, files_skipped=skipped,
            errors=errors, status=outcome, is_demo=True,
        )
        db.session.add(record)
        db.session.flush()
        for file_index in range(scanned):
            filename, category, size = FILES[(file_index + account_index * 2 + slot) % len(FILES)]
            if file_index >= len(FILES):
                path = PurePosixPath(filename)
                filename = f'{path.stem}_{file_index // len(FILES) + 1}{path.suffix}'
            destination = 'Programming/Python' if category == 'Python Projects' else 'University' if category == 'University Files' else category
            if record.mode == 'month':
                destination += '/' + started.strftime('%Y/%B')
            elif record.mode == 'extension':
                destination = PurePosixPath(filename).suffix.lstrip('.')
            elif record.mode == 'size':
                destination = 'Large' if size >= 100 * 1024**2 else 'Medium' if size >= 10 * 1024**2 else 'Small' if size >= 1024**2 else 'Tiny'
            status = 'ready' if is_preview else 'moved' if file_index < moved else 'skipped' if file_index < moved + skipped else 'error'
            reason = 'File is in use by another application.' if status == 'error' else 'Hidden or unsupported filesystem entry.' if status == 'skipped' else None
            db.session.add(FileOperation(
                session_id=record.id, original_path=demo_path(folder, filename),
                destination_path=demo_path(folder, *destination.split('/'), filename),
                filename=filename, extension=PurePosixPath(filename).suffix,
                category=category, file_size=size + (index % 4) * 1024,
                status=status, error=reason, created_at=started,
            ))


def _seed_schedules(user, now):
    from app.scheduler import next_occurrence
    for index, (name, folder, frequency, active) in enumerate((
        ('Downloads Daily Cleanup', FOLDERS[0], 'daily', True),
        ('Desktop Weekly Cleanup', FOLDERS[1], 'weekly', True),
        ('Documents Monthly Archive', FOLDERS[2], 'monthly', False),
    )):
        db.session.add(ScheduledTask(
            user_id=user.id, name=name, folder_path=folder, frequency=frequency,
            mode='month' if frequency == 'monthly' else 'type', is_active=active,
            is_demo=True, last_run=now - timedelta(days=index + 1),
            next_run=next_occurrence(now, frequency),
        ))


def _seed_logs(user, account_index, now):
    events = (
        ('User logged in', 'Signed in to the demo workspace.'),
        ('Created organization rule', 'Python Projects: Programming/Python.'),
        ('Scanned folder', 'Scanned 48 files in the fictional Downloads folder.'),
        ('Previewed organization', 'Reviewed planned destinations before organization.'),
        ('Organized 43 files', 'Downloads cleanup completed; 5 files skipped.'),
        ('Created scheduled task', 'Downloads Daily Cleanup added (demo only).'),
        ('Updated profile', 'Demo profile preferences updated.'),
        ('Undo operation completed', 'Restored an illustrative organization session.'),
    )
    if user.role == 'admin':
        events += (
            ('Admin viewed user management', 'Reviewed demo accounts and roles.'),
            ('Admin changed user status', 'Illustrative account status event; no real account changed.'),
        )
    for index, (action, details) in enumerate(events):
        db.session.add(ActivityLog(
            user_id=user.id, action=action, details=details,
            created_at=now - timedelta(days=index + account_index, minutes=index * 37),
        ))


def seed_demo():
    """Seed new demo identities once; preserve unrelated accounts and real data."""
    if current_app.config['SESSION_COOKIE_SECURE']:
        raise RuntimeError('Demo seeding is disabled in production.')
    initialize_database()
    seed_defaults()
    now = utcnow()
    skipped = []
    try:
        _upgrade_legacy_accounts()
        _normalize_legacy_paths()
        _retire_legacy_fixtures()
        for account_index, (username, email, role) in enumerate(ACCOUNTS):
            user = User.query.filter_by(username=username).first()
            if user and _has_marker(user.id, MARKER):
                continue
            if user:
                if user.email != email or not _has_marker(user.id, LEGACY_MARKER):
                    skipped.append(username)
                    continue
            elif User.query.filter_by(email=email).first():
                skipped.append(username)
                continue
            else:
                user = User(username=username, email=email, role=role, active=True,
                            password_hash=ADMIN_HASH if role == 'admin' else USER_HASH,
                            created_at=now - timedelta(days=60 + account_index * 8))
                db.session.add(user)
                db.session.flush()
            _seed_rules(user, now)
            _seed_sessions(user, account_index, now)
            _seed_schedules(user, now)
            _seed_logs(user, account_index, now)
            db.session.add(ActivityLog(user_id=user.id, action=MARKER,
                                      details='Fictional portfolio data; no filesystem operations performed.'))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    if skipped:
        current_app.logger.warning('Demo seed skipped existing unrelated identities: %s', ', '.join(skipped))
    account_ids = [user.id for name, _, _ in ACCOUNTS
                   if (user := User.query.filter_by(username=name).first()) and _has_marker(user.id, MARKER)]
    return {
        'demo accounts': len(account_ids),
        'demo sessions': OrganizationSession.query.filter(
            OrganizationSession.user_id.in_(account_ids), OrganizationSession.is_demo.is_(True)).count(),
        'demo schedules': ScheduledTask.query.filter(
            ScheduledTask.user_id.in_(account_ids), ScheduledTask.is_demo.is_(True)).count(),
        'skipped existing identities': len(skipped),
    }
