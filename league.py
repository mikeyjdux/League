import re
import secrets
import string

from flask import abort, g, session
from sqlalchemy import inspect, text

from models import Fixture, League, LeagueMembership, Season, Team, db


DEFAULT_LEAGUE_SLUG = 'default-league'
DEFAULT_SEASON_NAME = 'Current Season'
LEAGUE_ROLE_USER = 'user'
LEAGUE_ROLE_MODERATOR = 'moderator'
JOIN_CODE_ALPHABET = ''.join(ch for ch in string.ascii_uppercase + string.digits if ch not in {'0', 'O', '1', 'I'})
JOIN_CODE_LENGTH = 5


def slugify(value):
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return slug or DEFAULT_LEAGUE_SLUG


def build_unique_league_slug(name, requested_slug=''):
    base_slug = slugify(requested_slug or name)
    slug = base_slug
    suffix = 2

    while League.query.filter_by(slug=slug).first() is not None:
        slug = f'{base_slug}-{suffix}'
        suffix += 1

    return slug


def normalize_join_code(value):
    return ''.join((value or '').upper().split())


def generate_join_code():
    return ''.join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


def generate_unique_join_code():
    join_code = generate_join_code()
    while League.query.filter_by(join_code=join_code).first() is not None:
        join_code = generate_join_code()
    return join_code


def get_league_by_join_code(value):
    join_code = normalize_join_code(value)
    if not join_code:
        return None
    return League.query.filter_by(join_code=join_code).first()


def add_user_to_league(user, league, role=LEAGUE_ROLE_USER):
    membership = LeagueMembership.query.filter_by(user_id=user.id, league_id=league.id).first()
    if membership is not None:
        return membership, False

    membership = LeagueMembership()
    membership.user_id = user.id
    membership.league_id = league.id
    membership.role = role
    db.session.add(membership)
    return membership, True


def ensure_league_schema():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    if 'league' in table_names:
        league_columns = {column['name'] for column in inspector.get_columns('league')}
        if 'join_code' not in league_columns:
            db.session.execute(text('ALTER TABLE league ADD COLUMN join_code VARCHAR(16)'))
        db.session.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_league_join_code ON league (join_code)'))

    if 'league_membership' in table_names:
        membership_columns = {column['name'] for column in inspector.get_columns('league_membership')}
        if 'role' not in membership_columns:
            db.session.execute(text("ALTER TABLE league_membership ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
            if 'is_admin' in membership_columns:
                db.session.execute(text("UPDATE league_membership SET role = CASE WHEN is_admin THEN 'moderator' ELSE 'user' END"))

    if 'team' in table_names:
        team_columns = {column['name'] for column in inspector.get_columns('team')}
        if 'season_id' not in team_columns:
            db.session.execute(text('ALTER TABLE team ADD COLUMN season_id INTEGER'))
        db.session.execute(text('ALTER TABLE team DROP CONSTRAINT IF EXISTS team_name_key'))

    if 'fixture' in table_names:
        fixture_columns = {column['name'] for column in inspector.get_columns('fixture')}
        if 'season_id' not in fixture_columns:
            db.session.execute(text('ALTER TABLE fixture ADD COLUMN season_id INTEGER'))

    db.session.commit()


def sync_existing_league_data():
    leagues_without_codes = League.query.filter((League.join_code.is_(None)) | (League.join_code == '')).all()
    for existing_league in leagues_without_codes:
        existing_league.join_code = generate_unique_join_code()

    memberships_without_role = LeagueMembership.query.filter((LeagueMembership.role.is_(None)) | (LeagueMembership.role == '')).all()
    for membership in memberships_without_role:
        membership.role = LEAGUE_ROLE_USER

    db.session.commit()


def get_user_leagues(user):
    if user is None:
        return []

    cached_user_id = getattr(g, 'available_leagues_user_id', None)
    if cached_user_id == user.id:
        return g.available_leagues

    leagues = (
        League.query.join(LeagueMembership, LeagueMembership.league_id == League.id)
        .filter(LeagueMembership.user_id == user.id)
        .order_by(League.name.asc())
        .all()
    )
    g.available_leagues = leagues
    g.available_leagues_user_id = user.id
    return leagues


def create_league_with_admin(name, season_name, admin_user, requested_slug=''):
    league_name = name.strip()
    initial_season_name = season_name.strip() or DEFAULT_SEASON_NAME
    if not league_name:
        raise ValueError('League name is required.')
    if League.query.filter_by(name=league_name).first() is not None:
        raise ValueError('League name already exists.')

    league = League()
    league.name = league_name
    league.slug = build_unique_league_slug(league_name, requested_slug=requested_slug)
    league.join_code = generate_unique_join_code()
    db.session.add(league)
    db.session.flush()

    season = Season()
    season.league_id = league.id
    season.name = initial_season_name
    season.is_active = True
    db.session.add(season)
    db.session.flush()

    membership, _ = add_user_to_league(admin_user, league, role=LEAGUE_ROLE_MODERATOR)
    db.session.commit()
    return league, season, membership


def delete_league(league):
    season_ids = [season.id for season in Season.query.filter_by(league_id=league.id).all()]
    if season_ids:
        Fixture.query.filter(Fixture.season_id.in_(season_ids)).delete(synchronize_session=False)
        Team.query.filter(Team.season_id.in_(season_ids)).delete(synchronize_session=False)
        Season.query.filter(Season.id.in_(season_ids)).delete(synchronize_session=False)

    LeagueMembership.query.filter_by(league_id=league.id).delete(synchronize_session=False)
    db.session.delete(league)
    db.session.commit()


def get_user_admin_leagues(user):
    if user is None:
        return []

    cached_user_id = getattr(g, 'admin_leagues_user_id', None)
    if cached_user_id == user.id:
        return g.admin_leagues

    leagues = (
        League.query.join(LeagueMembership, LeagueMembership.league_id == League.id)
        .filter(LeagueMembership.user_id == user.id, LeagueMembership.role == LEAGUE_ROLE_MODERATOR)
        .order_by(League.name.asc())
        .all()
    )
    g.admin_leagues = leagues
    g.admin_leagues_user_id = user.id
    return leagues


def get_active_league_for_user(user):
    leagues = get_user_leagues(user)
    if not leagues:
        return None

    active_slug = session.get('active_league_slug')
    if active_slug:
        for league in leagues:
            if league.slug == active_slug:
                return league

    return leagues[0]


def get_active_season(league):
    if league is None:
        return None

    cached_season = getattr(g, 'current_season', None)
    if cached_season is not None and cached_season.league_id == league.id:
        return cached_season

    return (
        Season.query.filter_by(league_id=league.id)
        .order_by(Season.is_active.desc(), Season.created_at.desc())
        .first()
    )


def load_league_context(user, league_slug, require_manager=False):
    cached_context = getattr(g, 'loaded_league_context', None)
    if cached_context is not None:
        cached_user_id = cached_context['user_id']
        cached_league_slug = cached_context['league_slug']
        cached_requires_manager = cached_context['require_manager']
        if cached_user_id == user.id and cached_league_slug == league_slug and cached_requires_manager == require_manager:
            league = cached_context['league']
            season = cached_context['season']
            membership = cached_context['membership']
            g.current_league = league
            g.current_membership = membership
            g.current_season = season
            session['active_league_slug'] = league.slug
            return league, season, membership

    league = None
    membership = None

    if not user.is_admin or not require_manager:
        for user_league in get_user_leagues(user):
            if user_league.slug == league_slug:
                league = user_league
                break

        if league is None:
            if not user.is_admin:
                abort(404)
            league = League.query.filter_by(slug=league_slug).first()
            if league is None:
                abort(404)
        else:
            membership = LeagueMembership.query.filter_by(user_id=user.id, league_id=league.id).first()
    else:
        league = League.query.filter_by(slug=league_slug).first()
        if league is None:
            abort(404)

    if membership is None and league is not None and (user.is_admin and require_manager):
        membership = None
    elif membership is None:
        membership = LeagueMembership.query.filter_by(user_id=user.id, league_id=league.id).first()
        if membership is None:
            abort(404)

    if require_manager and not user.is_admin:
        if membership is None:
            abort(404)
        if membership.role != LEAGUE_ROLE_MODERATOR:
            abort(404)

    season = get_active_season(league)
    if season is None:
        season = Season()
        season.league_id = league.id
        season.name = DEFAULT_SEASON_NAME
        season.is_active = True
        db.session.add(season)
        db.session.commit()

    g.current_league = league
    g.current_membership = membership
    g.current_season = season
    g.loaded_league_context = {
        'user_id': user.id,
        'league_slug': league_slug,
        'require_manager': require_manager,
        'league': league,
        'season': season,
        'membership': membership,
    }
    session['active_league_slug'] = league.slug
    return league, season, membership


def build_standings(season):
    teams = Team.query.filter_by(season_id=season.id).order_by(Team.name.asc()).all()
    fixtures = (
        db.session.query(
            Fixture.home_team_id,
            Fixture.away_team_id,
            Fixture.home_goals,
            Fixture.away_goals,
        )
        .filter_by(season_id=season.id, played=True)
        .all()
    )

    table_map = {
        team.id: {
            'team': team.name,
            'played': 0,
            'won': 0,
            'drawn': 0,
            'lost': 0,
            'gf': 0,
            'ga': 0,
            'gd': 0,
            'points': 0,
        }
        for team in teams
    }

    for home_team_id, away_team_id, home_goals, away_goals in fixtures:
        home_stats = table_map.get(home_team_id)
        away_stats = table_map.get(away_team_id)
        if home_stats is None or away_stats is None:
            continue

        home_goals = home_goals or 0
        away_goals = away_goals or 0

        home_stats['played'] += 1
        away_stats['played'] += 1
        home_stats['gf'] += home_goals
        home_stats['ga'] += away_goals
        away_stats['gf'] += away_goals
        away_stats['ga'] += home_goals

        if home_goals > away_goals:
            home_stats['won'] += 1
            away_stats['lost'] += 1
            home_stats['points'] += 3
        elif away_goals > home_goals:
            away_stats['won'] += 1
            home_stats['lost'] += 1
            away_stats['points'] += 3
        else:
            home_stats['drawn'] += 1
            away_stats['drawn'] += 1
            home_stats['points'] += 1
            away_stats['points'] += 1

    table_data = list(table_map.values())
    for stats in table_data:
        stats['gd'] = stats['gf'] - stats['ga']

    table_data.sort(key=lambda row: (-row['points'], -row['gd'], -row['gf'], row['team'].lower()))
    return table_data
