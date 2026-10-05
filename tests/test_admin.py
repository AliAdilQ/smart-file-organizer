from app.extensions import db
from app.models import User


def test_admin_authorization(client, login):
    assert client.get('/admin/').status_code == 302
    login()
    for path in ['/admin/', '/admin/users', '/admin/rules', '/admin/logs']:
        assert client.get(path).status_code == 403
    client.post('/auth/logout')
    login('admin')
    for path in ['/admin/', '/admin/users', '/admin/rules', '/admin/logs', '/admin/users?q=admin&role=admin']:
        assert client.get(path).status_code == 200


def test_admin_self_protection_and_user_update(app, client, login):
    login('admin')
    with app.app_context():
        admin_id = User.query.filter_by(username='admin').one().id
        alice_id = User.query.filter_by(username='alice').one().id
    response = client.post(f'/admin/users/{admin_id}', data={'role': 'user'}, follow_redirects=True)
    assert b'cannot deactivate or demote' in response.data
    client.post(f'/admin/users/{alice_id}', data={'role': 'admin', 'active': 'yes'})
    with app.app_context():
        assert db.session.get(User, admin_id).active
        assert db.session.get(User, alice_id).role == 'admin'


def test_admin_category_edit(client, app, login):
    from app.models import OrganizationRule
    login('admin')
    client.post('/admin/rules', data={'name': 'Design', 'extensions': '.fig .psd', 'destination': 'Design', 'priority': 20, 'is_active': 'y'})
    with app.app_context():
        rule = OrganizationRule.query.filter_by(name='Design').one()
        rule_id = rule.id
    client.post(f'/admin/rules?edit={rule_id}', data={'name': 'Design files', 'extensions': '.fig', 'destination': 'Work/Design', 'priority': 20, 'is_active': 'y'})
    with app.app_context():
        assert db.session.get(OrganizationRule, rule_id).destination == 'Work/Design'
