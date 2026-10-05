import pytest
from app import create_app
from app.extensions import db
from app.models import User
from app.organizer.rules import seed_defaults


@pytest.fixture
def app(tmp_path):
    folder = tmp_path / 'downloads'
    folder.mkdir()
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-key',
                      'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'WTF_CSRF_ENABLED': False,
                      'ORGANIZER_ROOTS': [folder], 'PROTECTED_PATHS': []})
    with app.app_context():
        db.create_all()
        seed_defaults()
        for name, role in [('alice', 'user'), ('bob', 'user'), ('admin', 'admin')]:
            user = User(username=name, email=f'{name}@example.com', role=role)
            user.set_password('TestPassword123!')
            db.session.add(user)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def folder(app):
    return app.config['ORGANIZER_ROOTS'][0]


@pytest.fixture
def login(client):
    def sign_in(name='alice'):
        return client.post('/auth/login', data={'identity': name, 'password': 'TestPassword123!'}, follow_redirects=True)
    return sign_in
