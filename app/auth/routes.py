from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import User, utcnow
from app.auth.forms import LoginForm, RegisterForm
from app.audit import audit

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        identity = form.identity.data.strip()
        user = User.query.filter((User.username == identity) | (User.email == identity.lower())).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user)
            user.last_login = utcnow()
            audit(user.id, 'Login')
            db.session.commit()
            flash('Welcome back. Your workspace is ready.', 'success')
            return redirect(url_for('main.dashboard'))
        audit(None, 'Login rejected')
        db.session.commit()
        flash('Invalid credentials or inactive account.', 'danger')
    return render_template('auth/form.html', form=form, title='Welcome back', kind='login')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data.strip(), email=form.email.data.lower().strip())
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.flush()
            audit(user.id, 'Registered')
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('That username or email is already registered.', 'danger')
        else:
            flash('Account created. Sign in to get started.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/form.html', form=form, title='Make room for clarity', kind='register')


@bp.post('/logout')
@login_required
def logout():
    audit(current_user.id, 'Logout')
    db.session.commit()
    logout_user()
    return redirect(url_for('main.landing'))


@bp.get('/forgot-password')
def forgot_password():
    return render_template('auth/forgot.html')
