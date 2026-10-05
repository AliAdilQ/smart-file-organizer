from datetime import datetime
from types import SimpleNamespace
import pytest
from pathlib import Path
from app.organizer.rules import classify, available_rules, validate_destination, normalize_extensions
from app.models import OrganizationRule, User
from app.extensions import db


def test_rule_creation(app, client, login):
    login()
    client.post('/rules', data={'name': 'University', 'extensions': 'pdf, docx', 'destination': 'University/Notes', 'priority': '1', 'is_active': 'y'})
    with app.app_context():
        rule = OrganizationRule.query.filter_by(name='University').one()
        assert rule.extensions == '.docx .pdf'
        stat = SimpleNamespace(st_mtime=datetime(2025, 1, 15).timestamp(), st_size=1)
        assert classify(Path('a.pdf'), available_rules(rule.user_id), 'type', stat) == ('University', 'University/Notes')


@pytest.mark.parametrize('value', ['../outside', '/absolute', 'C:/Windows', 'a/../../b', 'CON', 'a/NUL', 'a/.git', 'a/..'])
def test_destination_traversal(value):
    with pytest.raises(ValueError):
        validate_destination(value)


def test_classification_modes(app):
    with app.app_context():
        rules = available_rules(1)
        stat = SimpleNamespace(st_mtime=datetime(2025, 1, 15).timestamp(), st_size=1024**2)
        assert classify(Path('a.PDF'), rules, 'type', stat) == ('Documents', 'Documents')
        assert classify(Path('a.xyz'), rules, 'type', stat)[1] == 'Other'
        assert classify(Path('a.pdf'), rules, 'year', stat)[1] == 'Documents/2025'
        assert classify(Path('a.pdf'), rules, 'month', stat)[1] == 'Documents/2025/January'
        assert classify(Path('a.pdf'), rules, 'extension', stat)[1] == 'pdf'
        assert classify(Path('a.pdf'), rules, 'size', stat)[1] == 'Small'


def test_other_user_rule_access(app, client, login):
    with app.app_context():
        bob = User.query.filter_by(username='bob').one()
        rule = OrganizationRule(user_id=bob.id, name='Private', extensions='.pdf', destination='Private')
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id
    login()
    assert client.post(f'/rules/{rule_id}/delete').status_code == 403
