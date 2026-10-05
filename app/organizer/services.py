"""Durable dry-run plans and conservative file moves.

No overwrite: reserve destination with O_EXCL, copy and verify, then unlink
the original only after a complete matching copy. A crash may leave a duplicate,
which is safer than losing the source. Moves are journaled before file I/O.
"""
import hashlib
import os
from pathlib import Path
import shutil
import threading
from datetime import timedelta
from flask import current_app
from app.extensions import db
from app.models import OrganizationSession, FileOperation, utcnow
from app.organizer.rules import available_rules, classify, MODES
from app.audit import audit

LOCK = threading.RLock()


def within(path, root):
    return path == root or root in path.parents


def safe_folder(value):
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise ValueError('Enter an absolute folder path on this server.')
    sensitive_names = {'.ssh', '.aws', '.azure', '.gnupg', '.git', '.codex', '.venv', 'venv'}
    if any(part.lower() in sensitive_names for part in raw.parts):
        raise ValueError('Credential, repository, and environment folders are protected.')
    # Reject symlink/junction components even if their targets are allowed.
    for part in (raw, *raw.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Linked folders are protected.')
    path = raw.resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Source must be a folder.')
    project = Path(current_app.root_path).parent.resolve()
    demo = project / 'demo_files' / 'sample_downloads'
    if within(path, project) and not within(path, demo):
        raise ValueError('Application source and configuration folders are protected.')
    system = [Path('/etc'), Path('/usr'), Path('/bin'), Path('/sbin'), Path('/var'), Path('/proc'), Path('/sys'), Path('/dev')]
    for env in ('WINDIR', 'PROGRAMFILES', 'PROGRAMFILES(X86)', 'PROGRAMDATA'):
        if os.getenv(env):
            system.append(Path(os.environ[env]))
    protected = system + [Path(p) for p in current_app.config['PROTECTED_PATHS']]
    if path == Path(path.anchor) or any(within(path, p.resolve()) or within(p.resolve(), path) for p in protected):
        raise ValueError('System folders and parents of protected folders cannot be organized.')
    roots = [Path(p).resolve() for p in current_app.config['ORGANIZER_ROOTS']]
    if not any(within(path, root) for root in roots):
        raise ValueError('Folder is not approved. Configure ORGANIZER_ROOTS in .env, then restart.')
    return path


def safe_target(source, destination):
    if not within(destination.resolve(), source) or destination == source:
        raise ValueError('Destination must remain inside the approved source folder.')
    for part in (destination, *destination.parents):
        if part == source:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Destination contains a linked folder or file.')


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def unique_path(path, reserved=None):
    reserved = reserved if reserved is not None else set()
    candidate, number = path, 1
    while candidate.exists() or candidate.is_symlink() or str(candidate).casefold() in reserved:
        candidate = path.with_name(f'{path.stem}_{number}{path.suffix}')
        number += 1
    reserved.add(str(candidate).casefold())
    return candidate


def preview(user_id, folder, mode='type', rule_id=None):
    if mode not in MODES:
        raise ValueError('Unknown organization mode.')
    source = safe_folder(folder)
    rules = available_rules(user_id)
    if rule_id:
        rules = [rule for rule in rules if rule.id == rule_id]
        if not rules:
            raise ValueError('Selected rule is unavailable.')
    entries = sorted(source.iterdir(), key=lambda p: p.name.lower())
    if len(entries) > current_app.config['MAX_SCAN_FILES']:
        raise ValueError('Folder exceeds the scan limit; split it into smaller folders.')
    session = OrganizationSession(user_id=user_id, source_folder=str(source), mode=mode)
    db.session.add(session)
    db.session.flush()
    reserved = set()
    for path in entries:
        if path.is_dir() and not path.is_symlink():
            continue  # Nonrecursive: existing category folders remain untouched.
        session.files_scanned += 1
        operation = FileOperation(session_id=session.id, original_path=str(path),
                                  destination_path=str(path), filename=path.name,
                                  extension=path.suffix.lower(), category='Other')
        db.session.add(operation)
        if path.is_symlink() or path.name.startswith('.') or not path.is_file():
            operation.status = 'skipped'
            operation.error = 'Hidden, linked, or nonregular file.'
            session.files_skipped += 1
            continue
        try:
            stat = path.stat()
            category, destination = classify(path, rules, mode, stat)
            target = source / destination / path.name
            safe_target(source, target)
            operation.file_size = stat.st_size
            operation.fingerprint = digest(path)
            operation.category = category
            operation.destination_path = str(unique_path(target, reserved))
        except (OSError, ValueError) as error:
            operation.status = 'skipped'
            operation.error = str(error)
            session.files_skipped += 1
    audit(user_id, 'Preview created', f'Session {session.id}: {session.files_scanned} files')
    db.session.commit()
    return session


def copy_move(original, destination, fingerprint):
    """Copy to an exclusively created destination, verify, then remove source."""
    if original.is_symlink() or not original.is_file() or digest(original) != fingerprint:
        raise ValueError('Source changed since preview; scan again.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents even a late collision from overwriting anything.
    with destination.open('xb') as target:
        with original.open('rb') as source:
            shutil.copyfileobj(source, target, 1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    if digest(destination) != fingerprint or digest(original) != fingerprint:
        raise ValueError('File changed during copy. Source retained; review the destination copy.')
    shutil.copystat(original, destination)
    original.unlink()


def execute(session):
    with LOCK:
        if session.status != 'preview' or session.is_demo:
            raise ValueError('This preview has already run or cannot be executed.')
        if session.started_at < utcnow() - timedelta(seconds=current_app.config['PREVIEW_TTL_SECONDS']):
            raise ValueError('Preview expired. Scan again before organizing.')
        source = safe_folder(session.source_folder)
        # Conditional state transition also guards repeated submissions across workers.
        claimed = OrganizationSession.query.filter_by(id=session.id, status='preview').update({'status': 'running'})
        db.session.commit()
        if not claimed:
            raise ValueError('Operation is already running.')
        for op in session.files:
            if op.status != 'ready':
                continue
            try:
                original = Path(op.original_path)
                if original.parent != source:
                    raise ValueError('Source no longer matches the approved preview.')
                safe_folder(str(source))
                target = Path(op.destination_path)
                safe_target(source, target)
                op.destination_path = str(unique_path(target))
                op.status = 'moving'
                db.session.commit()  # Write-ahead record for interrupted jobs.
                copy_move(original, Path(op.destination_path), op.fingerprint)
                op.status = 'moved'
                session.files_moved += 1
            except (OSError, ValueError) as error:
                op.status = 'error'
                op.error = str(error)
                session.errors += 1
                current_app.logger.warning('Move failed for file operation %s: %s', op.id, error)
            db.session.commit()
        session.status = 'partial' if session.errors and session.files_moved else ('failed' if session.errors else 'completed')
        session.completed_at = utcnow()
        audit(session.user_id, 'Organization complete', f'Session {session.id}: {session.files_moved} moved, {session.errors} errors')
        db.session.commit()
        return session


def undo(session):
    with LOCK:
        if session.is_demo or session.status not in ('completed', 'partial', 'undo_partial'):
            raise ValueError('This session cannot be undone.')
        source = safe_folder(session.source_folder)
        claimed = OrganizationSession.query.filter(
            OrganizationSession.id == session.id,
            OrganizationSession.status.in_(['completed', 'partial', 'undo_partial'])
        ).update({'status': 'undoing'}, synchronize_session=False)
        db.session.commit()
        if not claimed:
            raise ValueError('Session is already being changed.')
        for op in reversed(session.files):
            if op.status not in ('moved', 'undo_error'):
                continue
            try:
                original, destination = Path(op.original_path), Path(op.destination_path)
                safe_folder(str(source))
                safe_target(source, destination)
                if original.parent != source or original.exists() or original.is_symlink():
                    raise ValueError('Original location is occupied. File retained; resolve conflict and retry undo.')
                op.status = 'undoing'
                db.session.commit()
                copy_move(destination, original, op.fingerprint)
                op.status, op.error = 'undone', None
            except (OSError, ValueError) as error:
                op.status, op.error = 'undo_error', str(error)
            db.session.commit()
        session.status = 'undo_partial' if any(op.status == 'undo_error' for op in session.files) else 'undone'
        audit(session.user_id, 'Undo', f'Session {session.id}: {session.status}')
        db.session.commit()
        return session
