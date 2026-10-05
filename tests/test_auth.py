from app.extensions import db
from app.models import User


def test_register_login_logout(client, app):
    response = client.post('/auth/register', data={'username': 'new_user', 'email': 'new@example.com',
                                                 'password': 'Password123!', 'confirm': 'Password123!'}, follow_redirects=True)
    assert b'Account created' in response.data
    with app.app_context():
        user = User.query.filter_by(username='new_user').one()
        assert user.password_hash != 'Password123!'
        assert user.check_password('Password123!')
        assert user.role == 'user'
    assert client.post('/auth/login', data={'identity': 'new_user', 'password': 'Password123!'}).status_code == 302
    assert client.get('/dashboard').status_code == 200
    assert client.post('/auth/logout').status_code == 302
    assert client.get('/dashboard').status_code == 302


def test_invalid_login_and_duplicate(client, login):
    assert b'Invalid credentials' in client.post('/auth/login', data={'identity': 'alice', 'password': 'wrong'}, follow_redirects=True).data
    response = client.post('/auth/register', data={'username': 'alice', 'email': 'alice@example.com',
                                                 'password': 'Password123!', 'confirm': 'Password123!'}, follow_redirects=True)
    assert b'already registered' in response.data


def test_inactive_user_blocked(client, app, login):
    login()
    with app.app_context():
        user = User.query.filter_by(username='alice').one()
        user.active = False
        db.session.commit()
    assert client.get('/dashboard').status_code == 302
    assert b'Invalid credentials' in login().data


def test_csrf_enforced(app):
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()
    assert client.post('/auth/login', data={'identity': 'alice', 'password': 'TestPassword123!'}).status_code == 400
    assert client.get('/auth/logout').status_code == 405


def test_page_smoke(client, login):
    for path in ['/', '/auth/login', '/auth/register', '/auth/forgot-password', '/missing']:
        assert client.get(path).status_code in (200, 404)
    login()
    for path in ['/dashboard', '/organize/', '/rules', '/history', '/statistics', '/schedules', '/profile', '/settings']:
        assert client.get(path).status_code == 200, path


def test_profile_password_required(client, login):
    login()
    response = client.post('/profile', data={'email': 'new@example.com', 'current_password': 'bad', 'password': ''}, follow_redirects=True)
    assert b'incorrect' in response.data
