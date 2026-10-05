"""Application factory and CLI commands."""
import logging
import secrets
from logging.handlers import RotatingFileHandler
from pathlib import Path
import click
from flask import Flask, render_template
from flask_login import current_user, logout_user
from app.extensions import db, login_manager, csrf
from config import Config


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config['SESSION_COOKIE_SECURE'] and len(app.config.get('SECRET_KEY') or '') < 32:
        raise RuntimeError('Production requires a random SECRET_KEY of at least 32 characters.')
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        if app.config['SESSION_COOKIE_SECURE']:
            raise RuntimeError('Production requires SECRET_KEY.')
        key_path = Path(app.instance_path) / 'development-secret'
        if not key_path.exists():
            try:
                with key_path.open('x') as handle:
                    handle.write(secrets.token_hex(32))
            except FileExistsError:
                pass
        app.config['SECRET_KEY'] = key_path.read_text().strip()
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id)) if user_id.isdigit() else None

    @app.before_request
    def check_active():
        if current_user.is_authenticated and not current_user.is_active:
            logout_user()

    from app.auth.routes import bp as auth
    from app.main.routes import bp as main
    from app.organizer.routes import bp as organizer
    from app.admin.routes import bp as admin
    for bp in (auth, main, organizer, admin):
        app.register_blueprint(bp)

    for code in (400, 403, 404, 500):
        app.register_error_handler(code, lambda error: (render_template('error.html', code=error.code), error.code))

    @app.template_filter('filesize')
    def filesize(value):
        size = float(value or 0)
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if size < 1024 or unit == 'TB':
                return f'{size:.1f} {unit}'
            size /= 1024

    @app.cli.command('init-db')
    def init_db():
        from app.schema import initialize_database
        initialize_database()
        from app.organizer.rules import seed_defaults
        seed_defaults()
        click.echo('Database initialized with default rules.')

    @app.cli.command('seed-demo')
    def seed_demo_command():
        from app.demo import seed_demo
        seed_demo()
        click.echo('Development demo data seeded.')

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True)
    @click.option('--email', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, email, password):
        from email_validator import validate_email
        email = validate_email(email, check_deliverability=False).normalized
        if len(password) < 10 or not username.strip():
            raise click.ClickException('Use a username and a password with at least 10 characters.')
        if User.query.filter((User.username == username) | (User.email == email)).first():
            raise click.ClickException('Username or email already exists.')
        user = User(username=username.strip(), email=email, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo('Administrator created.')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        return response

    if not app.testing:
        log_dir = Path(app.root_path).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        handler = RotatingFileHandler(log_dir / 'app.log', maxBytes=1_000_000, backupCount=3)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
    return app
