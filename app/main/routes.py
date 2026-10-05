from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import OrganizationRule, OrganizationSession, ScheduledTask, utcnow
from app.forms import RuleForm, ProfileForm, ScheduleForm
from app.main.analytics import analytics
from app.organizer.rules import normalize_extensions, validate_destination, available_rules
from app.organizer.services import safe_folder
from app.audit import audit

bp = Blueprint('main', __name__)


@bp.get('/')
def landing():
    return render_template('landing.html')


@bp.get('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/index.html', stats=analytics(current_user.id), title='Dashboard')


@bp.get('/statistics')
@login_required
def statistics():
    return render_template('dashboard/index.html', stats=analytics(current_user.id), title='Statistics', statistics=True)


@bp.get('/history')
@login_required
def history():
    query = OrganizationSession.query.filter_by(user_id=current_user.id)
    query = filter_sessions(query)
    page = query.order_by(OrganizationSession.started_at.desc()).paginate(per_page=20, error_out=False)
    return render_template('dashboard/history.html', page=page)


def filter_sessions(query):
    if request.args.get('q'):
        query = query.filter(OrganizationSession.source_folder.contains(request.args['q']))
    if request.args.get('status'):
        query = query.filter_by(status=request.args['status'])
    if request.args.get('date'):
        try:
            date = datetime.strptime(request.args['date'], '%Y-%m-%d')
            from datetime import timedelta
            query = query.filter(OrganizationSession.started_at >= date, OrganizationSession.started_at < date + timedelta(days=1))
        except ValueError:
            flash('Use a valid date filter.', 'warning')
    return query


@bp.route('/rules', methods=['GET', 'POST'])
@login_required
def rules():
    form = RuleForm()
    if form.validate_on_submit():
        try:
            rule = OrganizationRule(user_id=current_user.id, name=form.name.data.strip(),
                                    extensions=normalize_extensions(form.extensions.data),
                                    destination=validate_destination(form.destination.data),
                                    priority=form.priority.data, is_active=form.is_active.data)
            db.session.add(rule)
            audit(current_user.id, 'Rule created', rule.name)
            db.session.commit()
            flash('Custom rule created.', 'success')
            return redirect(url_for('main.rules'))
        except ValueError as error:
            flash(str(error), 'danger')
    return render_template('dashboard/rules.html', form=form,
                           rules=OrganizationRule.query.filter((OrganizationRule.user_id == current_user.id) |
                           (OrganizationRule.user_id.is_(None))).order_by(OrganizationRule.priority).all())


@bp.post('/rules/<int:rule_id>/<action>')
@login_required
def rule_action(rule_id, action):
    rule = db.get_or_404(OrganizationRule, rule_id)
    if rule.user_id != current_user.id:
        abort(403)
    if action == 'toggle':
        rule.is_active = not rule.is_active
    elif action == 'delete':
        # Retain scheduled references; disable dependent schedules before deleting.
        for task in ScheduledTask.query.filter_by(rule_id=rule.id).all():
            task.rule_id, task.is_active = None, False
        db.session.delete(rule)
    else:
        abort(404)
    audit(current_user.id, 'Rule ' + action, rule.name)
    db.session.commit()
    flash('Rule updated.', 'success')
    return redirect(url_for('main.rules'))


@bp.route('/schedules', methods=['GET', 'POST'])
@login_required
def schedules():
    form = ScheduleForm()
    form.rule_id.choices = [(0, 'All active rules')] + [(r.id, r.name) for r in available_rules(current_user.id)]
    if form.validate_on_submit():
        try:
            folder = safe_folder(form.folder.data.strip())
            from app.scheduler import next_occurrence
            task = ScheduledTask(user_id=current_user.id, folder_path=str(folder),
                                 name=(form.name.data or '').strip() or 'Organization routine',
                                 frequency=form.frequency.data, mode=form.mode.data,
                                 rule_id=form.rule_id.data or None,
                                 next_run=next_occurrence(utcnow(), form.frequency.data))
            db.session.add(task)
            audit(current_user.id, 'Schedule created', task.folder_path)
            db.session.commit()
            flash('Schedule saved. Run the worker to process due tasks.', 'success')
            return redirect(url_for('main.schedules'))
        except (ValueError, OSError) as error:
            flash(str(error), 'danger')
    return render_template('dashboard/schedules.html', form=form,
                           tasks=ScheduledTask.query.filter_by(user_id=current_user.id).all())


@bp.post('/schedules/<int:task_id>/<action>')
@login_required
def schedule_action(task_id, action):
    task = db.get_or_404(ScheduledTask, task_id)
    if task.user_id != current_user.id:
        abort(403)
    if action == 'toggle':
        task.is_active = not task.is_active
        if task.is_active:
            from app.scheduler import next_occurrence
            task.next_run = next_occurrence(utcnow(), task.frequency)
    elif action == 'delete':
        db.session.delete(task)
    else:
        abort(404)
    audit(current_user.id, 'Schedule ' + action, f'Task {task_id}')
    db.session.commit()
    return redirect(url_for('main.schedules'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.email = form.email.data.lower().strip()
            if form.password.data:
                current_user.set_password(form.password.data)
            audit(current_user.id, 'Profile updated')
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Email is already registered.', 'danger')
            else:
                flash('Profile updated.', 'success')
                return redirect(url_for('main.profile'))
    if request.method == 'GET':
        form.email.data = current_user.email
    return render_template('dashboard/profile.html', form=form)


@bp.get('/settings')
@login_required
def settings():
    return render_template('dashboard/settings.html', roots=current_app.config['ORGANIZER_ROOTS'])
