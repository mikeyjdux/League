import os
from functools import wraps

from flask import Blueprint, g, redirect, render_template, request, session, url_for

from models import User, db


auth_bp = Blueprint('auth', __name__)


@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        if not g.user.is_admin:
            return redirect(url_for('index'))
        return view(*args, **kwargs)

    return wrapped_view


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if g.user is not None:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            error = 'Invalid username or password.'
        else:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))

    return render_template('login.html', error=error)


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


def ensure_admin_user():
    admin_count = User.query.filter_by(is_admin=True).count()
    if admin_count > 0:
        return

    is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER')
    username = os.environ.get('LEAGUE_ADMIN_USERNAME', 'admin')
    password = os.environ.get('LEAGUE_ADMIN_PASSWORD')

    if is_production and (not username or not password):
        raise RuntimeError('LEAGUE_ADMIN_USERNAME and LEAGUE_ADMIN_PASSWORD are required in production.')

    password = password or 'admin123'

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, is_admin=True)
        user.set_password(password)
        db.session.add(user)
    else:
        user.is_admin = True
        user.set_password(password)

    db.session.commit()
    if not is_production and 'LEAGUE_ADMIN_PASSWORD' not in os.environ:
        print('WARNING: Created default admin account with fallback password. Set LEAGUE_ADMIN_PASSWORD in production.')
