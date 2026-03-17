import os
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from league import add_user_to_league, get_league_by_join_code, normalize_join_code
from models import User, db


auth_bp = Blueprint('auth', __name__)


def redirect_to_login(join_code=''):
    if join_code:
        return redirect(url_for('auth.login', join_code=join_code))
    return redirect(url_for('auth.login'))


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()


def redirect_authenticated_user():
    if g.user is not None:
        return redirect(url_for('index'))
    return None


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
            return redirect_to_login()
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect_to_login()
        if not g.user.is_admin:
            return redirect(url_for('index'))
        return view(*args, **kwargs)

    return wrapped_view


def log_in_user(user):
    session.clear()
    session['user_id'] = user.id


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    invite_join_code = normalize_join_code(request.args.get('join_code', ''))
    authenticated_redirect = redirect_authenticated_user()
    if authenticated_redirect is not None:
        return authenticated_redirect

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = get_user_by_username(username)

        if not user or not user.check_password(password):
            error = 'Invalid username or password.'
        else:
            log_in_user(user)
            return redirect(url_for('index'))

    return render_template('login.html', error=error, invite_join_code=invite_join_code)


@auth_bp.route('/register', methods=['POST'])
def register():
    authenticated_redirect = redirect_authenticated_user()
    if authenticated_redirect is not None:
        return authenticated_redirect

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    join_code = normalize_join_code(request.form.get('join_code', ''))

    if not username or not password or not join_code:
        flash('Username, password, and a valid league code are required.', 'error')
        return redirect_to_login(join_code)

    if get_user_by_username(username) is not None:
        flash('That username is already taken.', 'error')
        return redirect_to_login(join_code)

    league = get_league_by_join_code(join_code)
    if league is None:
        flash('That league code is invalid.', 'error')
        return redirect_to_login(join_code)

    user = User()
    user.username = username
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    add_user_to_league(user, league)
    db.session.commit()

    log_in_user(user)
    flash(f'Account created. You joined {league.name}.', 'success')
    return redirect(url_for('league_dashboard', league_slug=league.slug))


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect_to_login()


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

    user = get_user_by_username(username)
    if user is None:
        user = User()
        user.username = username
        user.is_admin = True
        user.set_password(password)
        db.session.add(user)
    else:
        user.is_admin = True
        user.set_password(password)

    db.session.commit()
    if not is_production and 'LEAGUE_ADMIN_PASSWORD' not in os.environ:
        print('WARNING: Created default admin account with fallback password. Set LEAGUE_ADMIN_PASSWORD in production.')
