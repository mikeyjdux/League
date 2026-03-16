from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from auth import admin_required, login_required
from league import LEAGUE_ROLE_MODERATOR, create_league_with_admin, delete_league, get_user_admin_leagues, get_user_leagues, load_league_context
from models import Fixture, League, LeagueMembership, Team, User, db


admin_bp = Blueprint('admin', __name__)


def parse_optional_score(value):
    if value in (None, ''):
        return None

    score = int(value)
    if score < 0:
        raise ValueError('Scores cannot be negative.')
    return score

def prepare_admin_overview_context():
    leagues = League.query.order_by(League.name.asc()).all()
    user_league_ids = {membership.league_id for membership in g.user.memberships}
    for league in leagues:
        league.active_season = next((season for season in league.seasons if season.is_active), None)
        league.member_count = len(league.memberships)
        league.moderator_count = sum(1 for membership in league.memberships if membership.role == LEAGUE_ROLE_MODERATOR)
        league.user_has_access = league.id in user_league_ids
        if league.active_season is not None:
            league.team_count = Team.query.filter_by(season_id=league.active_season.id).count()
            league.fixture_count = Fixture.query.filter_by(season_id=league.active_season.id).count()
        else:
            league.team_count = 0
            league.fixture_count = 0

    users = User.query.order_by(User.username.asc()).all()
    for user in users:
        memberships = sorted(user.memberships, key=lambda membership: membership.league.name.lower())
        user.sorted_memberships = memberships
        user.membership_count = len(memberships)
        user.moderator_membership_count = sum(1 for membership in memberships if membership.role == LEAGUE_ROLE_MODERATOR)

    return leagues, users


def redirect_after_league_change(user):
    if user.is_admin:
        return redirect(url_for('admin.admin_overview'))

    moderator_leagues = get_user_admin_leagues(user)
    if moderator_leagues:
        return redirect(url_for('admin.league_manager', league_slug=moderator_leagues[0].slug))

    leagues = get_user_leagues(user)
    if leagues:
        return redirect(url_for('league_dashboard', league_slug=leagues[0].slug))

    session.pop('active_league_slug', None)
    return redirect(url_for('index'))


@admin_bp.route('/admin')
@admin_required
def admin_overview():
    leagues, users = prepare_admin_overview_context()
    return render_template('admin_overview.html', leagues=leagues, users=users)


@admin_bp.route('/leagues/create', methods=['POST'])
@admin_required
def create_league():
    league_name = request.form.get('league_name', '').strip()
    season_name = request.form.get('season_name', '').strip()
    slug = request.form.get('league_slug', '').strip()

    if not league_name:
        fallback_slug = request.form.get('return_league_slug', '').strip()
        if fallback_slug:
            return redirect(url_for('admin.league_manager', league_slug=fallback_slug))
        return redirect(url_for('index'))

    try:
        league, _, _ = create_league_with_admin(
            name=league_name,
            season_name=season_name,
            admin_user=g.user,
            requested_slug=slug,
        )
    except ValueError:
        fallback_slug = request.form.get('return_league_slug', '').strip()
        if fallback_slug:
            return redirect(url_for('admin.league_manager', league_slug=fallback_slug))
        return redirect(url_for('index'))

    flash(f'League created. Join code: {league.join_code}', 'success')
    return redirect(url_for('admin.league_manager', league_slug=league.slug))


@admin_bp.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_user_password_from_admin(user_id):
    user = User.query.get_or_404(user_id)
    password = request.form.get('new_password', '')
    if password:
        user.set_password(password)
        db.session.commit()
    return redirect(url_for('admin.admin_overview'))


@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user_from_admin(user_id):
    user = User.query.get_or_404(user_id)
    if g.user.id == user.id:
        return redirect(url_for('admin.admin_overview'))

    if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        return redirect(url_for('admin.admin_overview'))

    LeagueMembership.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.admin_overview'))


@admin_bp.route('/admin/memberships/<int:membership_id>/toggle_moderator', methods=['POST'])
@admin_required
def toggle_membership_moderator_from_admin(membership_id):
    membership = LeagueMembership.query.get_or_404(membership_id)
    make_moderator = request.form.get('make_moderator') == '1'

    membership.role = LEAGUE_ROLE_MODERATOR if make_moderator else 'user'
    db.session.commit()
    return redirect(url_for('admin.admin_overview'))


@admin_bp.route('/admin/memberships/<int:membership_id>/delete', methods=['POST'])
@admin_required
def delete_membership_from_admin(membership_id):
    membership = LeagueMembership.query.get_or_404(membership_id)

    db.session.delete(membership)
    db.session.commit()
    return redirect(url_for('admin.admin_overview'))


@admin_bp.route('/leagues/<league_slug>/delete', methods=['POST'])
@admin_required
def delete_league_from_admin(league_slug):
    league, _, _ = load_league_context(g.user, league_slug, require_manager=True)
    delete_league(league)
    return redirect_after_league_change(g.user)


@admin_bp.route('/leagues/<league_slug>/manage')
@login_required
def league_manager(league_slug):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)
    teams = Team.query.filter_by(season_id=season.id).order_by(Team.name.asc()).all()
    fixtures = (
        Fixture.query.filter_by(season_id=season.id)
        .order_by(Fixture.fixture_time.asc())
        .all()
    )
    users = (
        User.query.join(LeagueMembership, LeagueMembership.user_id == User.id)
        .filter(LeagueMembership.league_id == g.current_league.id)
        .order_by(User.username.asc())
        .all()
    )
    moderator_count = 0
    for user in users:
        user.league_is_moderator = any(
            membership.league_id == g.current_league.id and membership.role == LEAGUE_ROLE_MODERATOR
            for membership in user.memberships
        )
        if user.league_is_moderator:
            moderator_count += 1

    return render_template('admin.html', teams=teams, fixtures=fixtures, users=users, moderator_count=moderator_count)


@admin_bp.route('/leagues/<league_slug>/teams/<int:team_id>/delete', methods=['POST'])
@login_required
def delete_team(league_slug, team_id):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)
    team = Team.query.filter_by(id=team_id, season_id=season.id).first_or_404()
    Fixture.query.filter(
        Fixture.season_id == season.id,
        ((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id)),
    ).delete(synchronize_session=False)
    db.session.delete(team)
    db.session.commit()
    return redirect(url_for('admin.league_manager', league_slug=league_slug))


@admin_bp.route('/leagues/<league_slug>/fixtures/<int:fixture_id>/delete', methods=['POST'])
@login_required
def delete_fixture(league_slug, fixture_id):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)
    Fixture.query.filter_by(id=fixture_id, season_id=season.id).delete(synchronize_session=False)
    db.session.commit()
    return redirect(url_for('admin.league_manager', league_slug=league_slug))


@admin_bp.route('/leagues/<league_slug>/fixtures/<int:fixture_id>', methods=['POST'])
@login_required
def update_managed_fixture(league_slug, fixture_id):
    _, season, _ = load_league_context(g.user, league_slug, require_manager=True)
    fixture = Fixture.query.filter_by(id=fixture_id, season_id=season.id).first_or_404()

    try:
        fixture_time = datetime.strptime(request.form['fixture_time'], '%Y-%m-%dT%H:%M')
        home_goals = parse_optional_score(request.form.get('home_goals'))
        away_goals = parse_optional_score(request.form.get('away_goals'))
    except (KeyError, TypeError, ValueError):
        return redirect(url_for('admin.league_manager', league_slug=league_slug))

    if (home_goals is None) != (away_goals is None):
        return redirect(url_for('admin.league_manager', league_slug=league_slug))

    fixture.fixture_time = fixture_time
    fixture.home_goals = home_goals
    fixture.away_goals = away_goals
    fixture.played = home_goals is not None and away_goals is not None
    db.session.commit()
    return redirect(url_for('admin.league_manager', league_slug=league_slug))
