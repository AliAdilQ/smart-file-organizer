"""Persistent users, plans, moves, schedules, and audit events."""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), default='user', nullable=False)
    active = db.Column('is_active', db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime)

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class OrganizationRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(80), nullable=False)
    extensions = db.Column(db.String(512), nullable=False)
    destination = db.Column(db.String(240), nullable=False)
    priority = db.Column(db.Integer, default=100)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class OrganizationSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source_folder = db.Column(db.Text, nullable=False)
    mode = db.Column(db.String(20), default='type')
    started_at = db.Column(db.DateTime, default=utcnow)
    completed_at = db.Column(db.DateTime)
    files_scanned = db.Column(db.Integer, default=0)
    files_moved = db.Column(db.Integer, default=0)
    files_skipped = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    status = db.Column(db.String(24), default='preview')
    is_demo = db.Column(db.Boolean, default=False)
    user = db.relationship(User)
    files = db.relationship('FileOperation', backref='session', lazy=True, cascade='all, delete-orphan')


class FileOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('organization_session.id'), nullable=False)
    original_path = db.Column(db.Text, nullable=False)
    destination_path = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    extension = db.Column(db.String(64))
    file_size = db.Column(db.BigInteger, default=0)
    category = db.Column(db.String(80))
    status = db.Column(db.String(32), default='ready')
    fingerprint = db.Column(db.String(64))
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)


class ScheduledTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), default='Organization routine', nullable=False)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)
    folder_path = db.Column(db.Text, nullable=False)
    frequency = db.Column(db.String(16), nullable=False)
    mode = db.Column(db.String(20), default='type')
    rule_id = db.Column(db.Integer, db.ForeignKey('organization_rule.id'))
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime, nullable=False)
    last_error = db.Column(db.Text)
    user = db.relationship(User)


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship(User)
