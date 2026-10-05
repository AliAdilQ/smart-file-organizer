from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User, OrganizationRule, OrganizationSession, ActivityLog
from app.main.analytics import analytics
from app.main.routes import filter_sessions
from app.forms import RuleForm
from app.organizer.rules import normalize_extensions, validate_destination
from app.audit import audit

bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(function):
    @wraps(function)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            abort(403)
        return function(*args, **kwargs)
    return decorated


@bp.get('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html', stats=analytics(),
                           users=User.query.count(), active_rules=OrganizationRule.query.filter_by(is_active=True).count())


@bp.get('/users')
@admin_required
def users():
    query = User.query
    if request.args.get('q'):
        term = request.args['q']
        query = query.filter(User.username.contains(term) | User.email.contains(term))
    if request.args.get('role') in ('admin', 'user'):
        query = query.filter_by(role=request.args['role'])
    return render_template('admin/users.html', page=query.order_by(User.id).paginate(per_page=20, error_out=False))


@bp.post('/users/<int:user_id>')
@admin_required
def update_user(user_id):
    user = db.get_or_404(User, user_id)
    role = request.form.get('role')
    active = request.form.get('active') == 'yes'
    if role not in ('user', 'admin'):
        abort(400)
    if user.id == current_user.id and (role != 'admin' or not active):
        flash('You cannot deactivate or demote your own admin account.', 'warning')
    elif user.role == 'admin' and user.active and (role != 'admin' or not active) and User.query.filter_by(role='admin', active=True).count() <= 1:
        flash('At least one active administrator must remain.', 'warning')
    else:
        user.role, user.active = role, active
        audit(current_user.id, 'User updated', f'User {user.id}: {role}, active={active}')
        db.session.commit()
        flash('User updated.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/rules', methods=['GET', 'POST'])
@admin_required
def rules():
    form = RuleForm()
    editing = None
    if request.args.get('edit', type=int):
        editing = db.get_or_404(OrganizationRule, request.args.get('edit', type=int))
        if editing.user_id is not None:
            abort(403)
        if request.method == 'GET':
            form = RuleForm(obj=editing)
    if form.validate_on_submit():
        try:
            extensions = normalize_extensions(form.extensions.data)
            destination = validate_destination(form.destination.data)
            rule = editing or OrganizationRule(user_id=None)
            rule.name, rule.extensions, rule.destination = form.name.data.strip(), extensions, destination
            rule.priority, rule.is_active = form.priority.data, form.is_active.data
            db.session.add(rule)
            audit(current_user.id, 'Default rule saved', rule.name)
            db.session.commit()
            flash('Category saved.', 'success')
            return redirect(url_for('admin.rules'))
        except ValueError as error:
            flash(str(error), 'danger')
    return render_template('admin/rules.html', form=form, editing=editing,
                           rules=OrganizationRule.query.filter_by(user_id=None).order_by(OrganizationRule.priority).all())


@bp.post('/rules/<int:rule_id>/toggle')
@admin_required
def toggle_rule(rule_id):
    rule = db.get_or_404(OrganizationRule, rule_id)
    if rule.user_id is not None:
        abort(403)
    rule.is_active = not rule.is_active
    audit(current_user.id, 'Default rule toggled', rule.name)
    db.session.commit()
    return redirect(url_for('admin.rules'))


@bp.get('/logs')
@admin_required
def logs():
    sessions = filter_sessions(OrganizationSession.query).order_by(OrganizationSession.started_at.desc()).paginate(per_page=20, error_out=False)
    query = ActivityLog.query
    if request.args.get('q'):
        query = query.filter(ActivityLog.details.contains(request.args['q']) | ActivityLog.action.contains(request.args['q']))
    return render_template('admin/logs.html', page=sessions,
                           logs=query.order_by(ActivityLog.created_at.desc()).limit(100).all())


@bp.get('/sessions/<int:session_id>')
@admin_required
def detail(session_id):
    from app.organizer.rules import MODES
    return render_template('organizer/detail.html', record=db.get_or_404(OrganizationSession, session_id), modes=MODES, read_only=True)
