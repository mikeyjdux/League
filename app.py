import os
from typing import Any, cast
from datetime import datetime

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy.orm import joinedload
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from admin import admin_bp
from auth import auth_bp, ensure_admin_user, login_required, redirect_to_login
from league import (
    sync_existing_league_data,
    build_standings,
    ensure_league_schema,
    get_league_by_join_code,
    get_active_league_for_user,
    get_user_leagues,
    load_league_context,
    add_user_to_league,
    parse_score_value,
)
from models import Fixture, Team, db


def env_flag(name):
    value = os.environ.get(name, '')
    return value.lower() in {'1', 'true', 'yes', 'on'}


app = Flask(__name__)
csrf = CSRFProtect(app)
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
        'csrf_token': generate_csrf,
    }


def redirect_to_league_dashboard(league_slug):
    return redirect(url_for('league_dashboard', league_slug=league_slug))


def get_season_fixture_or_404(season_id, fixture_id):
    return Fixture.query.filter_by(id=fixture_id, season_id=season_id).first_or_404()


def join_current_user_to_league(league):
    _, created = add_user_to_league(g.user, league)
    if created:
        db.session.commit()
        flash(f'You joined {league.name}.', 'success')
    else:
        flash(f'You already belong to {league.name}.', 'error')

    session['active_league_slug'] = league.slug


@app.route('/')
@login_required
def index():
    league = get_active_league_for_user(g.user)
    if league is None:
        return render_template('index.html', table=[], upcoming=[], results=[])
    return redirect_to_league_dashboard(league.slug)


@app.route('/leagues/<league_slug>/')
@login_required
def league_dashboard(league_slug):
    _, season, _ = load_league_context(g.user, league_slug)

    table_data = build_standings(season)
    fixtures = (
        Fixture.query.options(
            joinedload(cast(Any, Fixture.home_team)),  # pyright: ignore[reportArgumentType]
            joinedload(cast(Any, Fixture.away_team)),  # pyright: ignore[reportArgumentType]
        )
        .filter_by(season_id=season.id)
        .order_by(Fixture.fixture_time.asc())
        .all()
    )
    upcoming = [fixture for fixture in fixtures if not fixture.played]
    results = [fixture for fixture in reversed(fixtures) if fixture.played]
    return render_template('index.html', table=table_data, upcoming=upcoming, results=results)


@app.route('/leagues/<league_slug>/fixtures/<int:fixture_id>/result', methods=['POST'])
@login_required
def submit_fixture_result(league_slug, fixture_id):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)

    fixture = get_season_fixture_or_404(season.id, fixture_id)

    if fixture.played:
        return redirect_to_league_dashboard(league_slug)

    try:
        fixture.home_goals = parse_score_value(request.form.get('home_goals', ''))
        fixture.away_goals = parse_score_value(request.form.get('away_goals', ''))
    except (TypeError, ValueError):
        return redirect_to_league_dashboard(league_slug)

    fixture.played = True
    db.session.commit()
    return redirect_to_league_dashboard(league_slug)


@app.route('/leagues/<league_slug>/teams', methods=['POST'])
@login_required
def add_team(league_slug):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)

    name = request.form.get('team_name', '').strip()
    if not name:
        return redirect_to_league_dashboard(league_slug)

    existing_team = Team.query.filter_by(season_id=season.id, name=name).first()
    if existing_team is not None:
        return redirect_to_league_dashboard(league_slug)

    existing_team_ids = [team_id for team_id, in db.session.query(Team.id).filter_by(season_id=season.id).all()]

    new_team = Team()
    new_team.name = name
    new_team.season_id = season.id
    db.session.add(new_team)
    db.session.flush()

    if existing_team_ids:
        fixture_rows = []
        for team_id in existing_team_ids:
            fixture_rows.append(
                {
                    'season_id': season.id,
                    'home_team_id': team_id,
                    'away_team_id': new_team.id,
                }
            )
            fixture_rows.append(
                {
                    'season_id': season.id,
                    'home_team_id': new_team.id,
                    'away_team_id': team_id,
                }
            )
        db.session.bulk_insert_mappings(cast(Any, Fixture), fixture_rows)

    db.session.commit()
    return redirect_to_league_dashboard(league_slug)


@app.route('/leagues/<league_slug>/fixtures/<int:fixture_id>/schedule', methods=['POST'])
@login_required
def reschedule_fixture(league_slug, fixture_id):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)

    fixture = get_season_fixture_or_404(season.id, fixture_id)
    fixture_date = request.form.get('fixture_date', '').strip()

    if fixture.played or not fixture_date:
        return redirect_to_league_dashboard(league_slug)

    try:
        fixture.fixture_time = datetime.strptime(fixture_date, '%Y-%m-%dT%H:%M')
    except ValueError:
        return redirect_to_league_dashboard(league_slug)

    db.session.commit()
    return redirect_to_league_dashboard(league_slug)


@app.route('/leagues/join', methods=['POST'])
@login_required
def join_league():
    join_code = request.form.get('join_code', '')
    league = get_league_by_join_code(join_code)
    if league is None:
        flash('That league code is invalid.', 'error')
        return redirect(url_for('index'))

    join_current_user_to_league(league)
    return redirect_to_league_dashboard(league.slug)


@app.route('/join/<join_code>')
def join_league_from_link(join_code):
    league = get_league_by_join_code(join_code)
    if league is None:
        flash('That league code is invalid.', 'error')
        if getattr(g, 'user', None) is None:
            return redirect_to_login()
        return redirect(url_for('index'))

    if getattr(g, 'user', None) is None:
        return redirect_to_login(league.join_code)

    join_current_user_to_league(league)
    return redirect_to_league_dashboard(league.slug)


@app.errorhandler(404)
def handle_not_found(_error):
    if getattr(g, 'user', None) is None:
        return redirect_to_login()

    league = get_active_league_for_user(g.user)
    if league is not None:
        return redirect_to_league_dashboard(league.slug)

    return redirect(url_for('index'))


@app.errorhandler(CSRFError)
def handle_csrf_error(_error):
    flash('Your session expired or the form token was invalid. Please try again.', 'error')
    if getattr(g, 'user', None) is None:
        return redirect_to_login()

    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
