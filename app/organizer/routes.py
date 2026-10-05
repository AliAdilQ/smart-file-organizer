from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import OrganizationSession
from app.forms import OrganizerForm
from app.organizer.services import preview, execute, undo
from app.organizer.rules import MODES

bp = Blueprint('organizer', __name__, url_prefix='/organize')


def owned_session(session_id):
    record = db.get_or_404(OrganizationSession, session_id)
    if record.user_id != current_user.id:
        abort(403)
    return record


@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    form = OrganizerForm()
    if form.validate_on_submit():
        try:
            record = preview(current_user.id, form.folder.data.strip(), form.mode.data)
        except (ValueError, OSError) as error:
            db.session.rollback()
            flash(str(error), 'danger')
        else:
            return redirect(url_for('organizer.detail', session_id=record.id))
    example = OrganizationSession.query.filter_by(
        user_id=current_user.id, is_demo=True, status='preview'
    ).first()
    return render_template('organizer/index.html', form=form, demo_preview=example)


@bp.get('/sessions/<int:session_id>')
@login_required
def detail(session_id):
    return render_template('organizer/detail.html', record=owned_session(session_id), modes=MODES)


@bp.post('/sessions/<int:session_id>/execute')
@login_required
def run(session_id):
    record = owned_session(session_id)
    if request.form.get('confirm') != 'yes':
        abort(400)
    try:
        execute(record)
        flash(f'Organization {record.status}: {record.files_moved} files moved.', 'success' if not record.errors else 'warning')
    except (ValueError, OSError) as error:
        flash(str(error), 'danger')
    return redirect(url_for('organizer.detail', session_id=session_id))


@bp.post('/sessions/<int:session_id>/cancel')
@login_required
def cancel(session_id):
    record = owned_session(session_id)
    if record.is_demo:
        abort(400)
    if record.status == 'preview':
        record.status = 'cancelled'
        db.session.commit()
    return redirect(url_for('main.history'))


@bp.post('/sessions/<int:session_id>/undo')
@login_required
def reverse(session_id):
    try:
        result = undo(owned_session(session_id))
        flash('Undo complete.' if result.status == 'undone' else 'Some files could not be restored. Review the details.',
              'success' if result.status == 'undone' else 'warning')
    except (ValueError, OSError) as error:
        flash(str(error), 'danger')
    return redirect(url_for('organizer.detail', session_id=session_id))
