import os
from datetime import datetime

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from admin import admin_bp
from auth import auth_bp, ensure_admin_user, login_required
from league import (
    sync_existing_league_data,
    build_standings,
    ensure_league_schema,
    get_league_by_join_code,
    get_active_league_for_user,
    get_user_leagues,
    load_league_context,
    add_user_to_league,
)
from models import Fixture, Team, db


def env_flag(name):
    value = os.environ.get(name, '')
    return value.lower() in {'1', 'true', 'yes', 'on'}


app = Flask(__name__)
is_production = os.environ.get('FLASK_ENV') == 'production' or env_flag('RENDER')
secret_key = os.environ.get('SECRET_KEY')
if is_production and not secret_key:
    raise RuntimeError('SECRET_KEY is required in production.')

app.config['SECRET_KEY'] = secret_key or 'dev-secret-key-change-me'
database_url = os.environ.get('DATABASE_URL', '').strip()
if not database_url:
    raise RuntimeError('DATABASE_URL is required and must point to a PostgreSQL database.')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://') and '+psycopg' not in database_url:
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = is_production

db.init_app(app)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)


with app.app_context():
    db.create_all()
    ensure_league_schema()
    ensure_admin_user()
    sync_existing_league_data()


@app.context_processor
def inject_league_navigation():
    return {
        'available_leagues': get_user_leagues(getattr(g, 'user', None)),
        'current_league': getattr(g, 'current_league', None),
        'current_season': getattr(g, 'current_season', None),
        'current_membership': getattr(g, 'current_membership', None),
    }


def parse_score(value):
    score = int(value)
    if score < 0:
        raise ValueError('Scores cannot be negative.')
    return score


@app.route('/')
@login_required
def index():
    league = get_active_league_for_user(g.user)
    if league is None:
        return render_template('index.html', table=[], upcoming=[], results=[])
    return redirect(url_for('league_dashboard', league_slug=league.slug))


@app.route('/leagues/<league_slug>/')
@login_required
def league_dashboard(league_slug):
    _, season, _ = load_league_context(g.user, league_slug)

    table_data = build_standings(season)
    upcoming = (
        Fixture.query.filter_by(season_id=season.id, played=False)
        .order_by(Fixture.fixture_time.asc())
        .all()
    )
    results = (
        Fixture.query.filter_by(season_id=season.id, played=True)
        .order_by(Fixture.fixture_time.desc())
        .all()
    )
    return render_template('index.html', table=table_data, upcoming=upcoming, results=results)


@app.route('/leagues/<league_slug>/fixtures/<int:fixture_id>/result', methods=['POST'])
@login_required
def submit_fixture_result(league_slug, fixture_id):
    _, season, membership = load_league_context(g.user, league_slug)
    if not g.user.is_admin and (membership is None or membership.role != 'moderator'):
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    fixture = Fixture.query.filter_by(id=fixture_id, season_id=season.id).first_or_404()

    if fixture.played:
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    try:
        fixture.home_goals = parse_score(request.form.get('home_goals', ''))
        fixture.away_goals = parse_score(request.form.get('away_goals', ''))
    except (TypeError, ValueError):
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    fixture.played = True
    db.session.commit()
    return redirect(url_for('league_dashboard', league_slug=league_slug))


@app.route('/leagues/<league_slug>/teams', methods=['POST'])
@login_required
def add_team(league_slug):
    _, season, membership = load_league_context(g.user, league_slug)
    if not g.user.is_admin and (membership is None or membership.role != 'moderator'):
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    name = request.form.get('team_name', '').strip()
    if not name:
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    existing_team = Team.query.filter_by(season_id=season.id, name=name).first()
    if existing_team is not None:
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    new_team = Team()
    new_team.name = name
    new_team.season_id = season.id
    db.session.add(new_team)
    db.session.flush()

    existing_teams = Team.query.filter(Team.season_id == season.id, Team.id != new_team.id).all()
    for team in existing_teams:
        home_fixture = Fixture()
        home_fixture.season_id = season.id
        home_fixture.home_team_id = team.id
        home_fixture.away_team_id = new_team.id
        away_fixture = Fixture()
        away_fixture.season_id = season.id
        away_fixture.home_team_id = new_team.id
        away_fixture.away_team_id = team.id
        db.session.add(home_fixture)
        db.session.add(away_fixture)

    db.session.commit()
    return redirect(url_for('league_dashboard', league_slug=league_slug))


@app.route('/leagues/<league_slug>/fixtures/<int:fixture_id>/schedule', methods=['POST'])
@login_required
def reschedule_fixture(league_slug, fixture_id):
    _, season, membership = load_league_context(g.user, league_slug)
    if not g.user.is_admin and (membership is None or membership.role != 'moderator'):
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    fixture = Fixture.query.filter_by(id=fixture_id, season_id=season.id).first_or_404()
    fixture_date = request.form.get('fixture_date', '').strip()

    if fixture.played or not fixture_date:
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    try:
        fixture.fixture_time = datetime.strptime(fixture_date, '%Y-%m-%dT%H:%M')
    except ValueError:
        return redirect(url_for('league_dashboard', league_slug=league_slug))

    db.session.commit()
    return redirect(url_for('league_dashboard', league_slug=league_slug))


@app.route('/leagues/join', methods=['POST'])
@login_required
def join_league():
    join_code = request.form.get('join_code', '')
    league = get_league_by_join_code(join_code)
    if league is None:
        flash('That league code is invalid.', 'error')
        return redirect(url_for('index'))

    membership, created = add_user_to_league(g.user, league)
    if not created:
        flash(f'You already belong to {league.name}.', 'error')
        return redirect(url_for('league_dashboard', league_slug=league.slug))

    db.session.commit()
    session['active_league_slug'] = league.slug
    flash(f'You joined {league.name}.', 'success')
    return redirect(url_for('league_dashboard', league_slug=league.slug))


@app.route('/join/<join_code>')
def join_league_from_link(join_code):
    league = get_league_by_join_code(join_code)
    if league is None:
        flash('That league code is invalid.', 'error')
        if getattr(g, 'user', None) is None:
            return redirect(url_for('auth.login'))
        return redirect(url_for('index'))

    if getattr(g, 'user', None) is None:
        return redirect(url_for('auth.login', join_code=league.join_code))

    membership, created = add_user_to_league(g.user, league)
    if created:
        db.session.commit()
        flash(f'You joined {league.name}.', 'success')
    else:
        flash(f'You already belong to {league.name}.', 'error')

    session['active_league_slug'] = league.slug
    return redirect(url_for('league_dashboard', league_slug=league.slug))


@app.errorhandler(404)
def handle_not_found(_error):
    if getattr(g, 'user', None) is None:
        return redirect(url_for('auth.login'))

    league = get_active_league_for_user(g.user)
    if league is not None:
        return redirect(url_for('league_dashboard', league_slug=league.slug))

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
