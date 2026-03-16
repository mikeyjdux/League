from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class League(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    join_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    seasons = db.relationship('Season', back_populates='league', cascade='all, delete-orphan')
    memberships = db.relationship('LeagueMembership', back_populates='league', cascade='all, delete-orphan')


class Season(db.Model):
    __table_args__ = (db.UniqueConstraint('league_id', 'name', name='uq_season_league_name'),)

    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    league = db.relationship('League', back_populates='seasons')
    teams = db.relationship('Team', back_populates='season')
    fixtures = db.relationship('Fixture', back_populates='season')


class LeagueMembership(db.Model):
    __table_args__ = (db.UniqueConstraint('user_id', 'league_id', name='uq_membership_user_league'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'), nullable=False, index=True)
    role = db.Column(db.String(20), default='user', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='memberships')
    league = db.relationship('League', back_populates='memberships')


class Team(db.Model):
    __table_args__ = (db.UniqueConstraint('season_id', 'name', name='uq_team_season_name'),)

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), index=True)
    name = db.Column(db.String(80), nullable=False)

    season = db.relationship('Season', back_populates='teams')


class Fixture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), index=True)
    home_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    fixture_time = db.Column(db.DateTime, default=datetime.utcnow)
    home_goals = db.Column(db.Integer)
    away_goals = db.Column(db.Integer)
    played = db.Column(db.Boolean, default=False)

    season = db.relationship('Season', back_populates='fixtures')
    home_team = db.relationship('Team', foreign_keys=[home_team_id])
    away_team = db.relationship('Team', foreign_keys=[away_team_id])


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    memberships = db.relationship('LeagueMembership', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
