from datetime import timedelta
import pytest
from app.extensions import db
from app.models import User, OrganizationSession, utcnow
from app.organizer.services import preview, execute, undo, safe_folder, copy_move, digest


def test_preview_move_collision_undo(app, folder):
    file = folder / 'report.pdf'
    file.write_text('original')
    (folder / 'Documents').mkdir()
    (folder / 'Documents' / 'report.pdf').write_text('existing')
    with app.app_context():
        record = preview(1, str(folder))
        assert file.read_text() == 'original'
        assert record.files[0].destination_path.endswith('report_1.pdf')
        execute(record)
        assert not file.exists()
        assert (folder / 'Documents' / 'report.pdf').read_text() == 'existing'
        assert (folder / 'Documents' / 'report_1.pdf').read_text() == 'original'
        undo(record)
        assert record.status == 'undone'
        assert file.read_text() == 'original'
        with pytest.raises(ValueError):
            execute(record)


def test_changed_file_retained(app, folder):
    file = folder / 'report.pdf'
    file.write_text('before')
    with app.app_context():
        record = preview(1, str(folder))
        file.write_text('changed')
        execute(record)
        assert record.status == 'failed'
        assert file.read_text() == 'changed'


def test_undo_conflict_and_retry(app, folder):
    file = folder / 'report.pdf'
    file.write_text('original')
    with app.app_context():
        record = preview(1, str(folder))
        execute(record)
        file.write_text('new occupant')
        undo(record)
        assert record.status == 'undo_partial'
        assert file.read_text() == 'new occupant'
        assert (folder / 'Documents' / 'report.pdf').read_text() == 'original'
        file.unlink()  # Only a test fixture in pytest's temporary directory.
        undo(record)
        assert record.status == 'undone'
        assert file.read_text() == 'original'


def test_undo_changed_destination(app, folder):
    (folder / 'file.txt').write_text('original')
    with app.app_context():
        record = preview(1, str(folder))
        execute(record)
        (folder / 'Documents' / 'file.txt').write_text('edited')
        undo(record)
        assert record.status == 'undo_partial'
        assert not (folder / 'file.txt').exists()


def test_late_collision(app, folder):
    (folder / 'photo.jpg').write_text('photo')
    with app.app_context():
        record = preview(1, str(folder))
        (folder / 'Images').mkdir()
        (folder / 'Images' / 'photo.jpg').write_text('other')
        execute(record)
        assert (folder / 'Images' / 'photo.jpg').read_text() == 'other'
        assert (folder / 'Images' / 'photo_1.jpg').read_text() == 'photo'


def test_exclusive_move_never_overwrites(tmp_path):
    source = tmp_path / 'a.txt'
    destination = tmp_path / 'b.txt'
    source.write_text('source')
    destination.write_text('destination')
    with pytest.raises(FileExistsError):
        copy_move(source, destination, digest(source))
    assert source.read_text() == 'source'
    assert destination.read_text() == 'destination'


def test_protected_and_unapproved_paths(app, folder):
    with app.app_context():
        sensitive = folder / '.ssh'
        sensitive.mkdir()
        with pytest.raises(ValueError, match='protected'):
            safe_folder(str(sensitive))
        for path in [app.root_path, str(folder.parent), folder.anchor, 'relative/path']:
            with pytest.raises((ValueError, OSError)):
                safe_folder(path)


def test_expired_preview_and_cancel(app, folder, client, login):
    (folder / 'a.txt').write_text('a')
    with app.app_context():
        record = preview(1, str(folder))
        record.started_at = utcnow() - timedelta(hours=1)
        db.session.commit()
        with pytest.raises(ValueError, match='expired'):
            execute(record)
        record_id = record.id
    login()
    assert client.post(f'/organize/sessions/{record_id}/cancel').status_code == 302
    with app.app_context():
        assert db.session.get(OrganizationSession, record_id).status == 'cancelled'


def test_session_authorization(app, folder, client, login):
    (folder / 'a.txt').write_text('a')
    with app.app_context():
        bob = User.query.filter_by(username='bob').one()
        record_id = preview(bob.id, str(folder)).id
    login()
    assert client.get(f'/organize/sessions/{record_id}').status_code == 403
    assert client.post(f'/organize/sessions/{record_id}/execute', data={'confirm': 'yes'}).status_code == 403


def test_browser_preview_confirm_undo(client, login, folder, app):
    login()
    (folder / 'a.txt').write_text('test')
    response = client.post('/organize/', data={'folder': str(folder), 'mode': 'type'})
    location = response.headers['Location']
    assert b'Review your organization plan' in client.get(location).data
    assert client.post(location + '/execute').status_code == 400
    assert client.post(location + '/execute', data={'confirm': 'yes'}).status_code == 302
    assert (folder / 'Documents' / 'a.txt').exists()
    client.post(location + '/undo')
    assert (folder / 'a.txt').read_text() == 'test'


def test_hidden_files_skipped_nonrecursive(app, folder):
    (folder / '.secret.txt').write_text('private')
    (folder / 'nested').mkdir()
    (folder / 'nested' / 'nested.txt').write_text('nested')
    with app.app_context():
        record = preview(1, str(folder))
        assert record.files_scanned == 1
        assert record.files_skipped == 1
        execute(record)
        assert (folder / '.secret.txt').exists()
        assert (folder / 'nested' / 'nested.txt').exists()


def test_symlink_destination_blocked(app, folder, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    try:
        (folder / 'Documents').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('OS does not permit symlink creation.')
    (folder / 'a.txt').write_text('safe')
    with app.app_context():
        record = preview(1, str(folder))
        assert record.files_skipped >= 1
        execute(record)
        assert (folder / 'a.txt').exists()
        assert list(outside.iterdir()) == []
