from flask import Blueprint, render_template, request, redirect, url_for, g
from datetime import datetime
from models import Team, Fixture, User, db
from auth import admin_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin-panel')
@admin_required
def admin_panel():
    teams = Team.query.all()
    fixtures = Fixture.query.order_by(Fixture.fixture_time).all()
    users = User.query.order_by(User.username.asc()).all()
    return render_template('admin.html', teams=teams, fixtures=fixtures, users=users)

@admin_bp.route('/delete_team/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    # Remove related fixtures
    Fixture.query.filter((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id)).delete()
    db.session.delete(team)
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/delete_fixture/<int:fixture_id>', methods=['POST'])
@admin_required
def delete_fixture(fixture_id):
    Fixture.query.filter_by(id=fixture_id).delete()
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/update_fixture/<int:fixture_id>', methods=['POST'])
@admin_required
def update_fixture(fixture_id):
    fixture = Fixture.query.get_or_404(fixture_id)
    fixture.home_goals = request.form.get('home_goals') or None
    fixture.away_goals = request.form.get('away_goals') or None
    fixture.fixture_time = datetime.strptime(request.form['fixture_time'], '%Y-%m-%dT%H:%M')
    fixture.played = fixture.home_goals is not None and fixture.away_goals is not None
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/reset_league', methods=['POST'])
@admin_required
def reset_league():
    Fixture.query.delete()
    Team.query.delete()
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    is_admin = request.form.get('is_admin') == 'on'

    if not username or not password:
        return redirect(url_for('admin.admin_panel'))

    existing = User.query.filter_by(username=username).first()
    if existing is not None:
        return redirect(url_for('admin.admin_panel'))

    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    password = request.form.get('new_password', '')
    if password:
        user.set_password(password)
        db.session.commit()
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/users/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def toggle_user_admin(user_id):
    user = User.query.get_or_404(user_id)
    make_admin = request.form.get('make_admin') == '1'

    if not make_admin and user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return redirect(url_for('admin.admin_panel'))
        if g.user.id == user.id:
            return redirect(url_for('admin.admin_panel'))

    user.is_admin = make_admin
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if g.user.id == user.id:
        return redirect(url_for('admin.admin_panel'))

    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return redirect(url_for('admin.admin_panel'))

    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))
