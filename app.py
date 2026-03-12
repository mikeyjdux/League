from flask import Flask, render_template, request, redirect, url_for, g
from models import db, Team, Fixture
import os
from admin import admin_bp
from auth import auth_bp, login_required, admin_required, ensure_admin_user


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
#    ensure_admin_user()


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # Handle POST request to update fixture scores
    if request.method == 'POST':
        fixture_id = int(request.form['fixture_id'])
        fixture = Fixture.query.get(fixture_id)
        if fixture and not fixture.played:
            fixture.home_goals = int(request.form['home_goals'])
            fixture.away_goals = int(request.form['away_goals'])
            fixture.played = True
            db.session.commit()
        return redirect(url_for('index'))

    # Retrieve all teams and calculate their statistics
    teams = Team.query.all()
    table_data = []

    for team in teams:
        played = won = drawn = lost = gf = ga = pts = 0
        fixtures = Fixture.query.filter(
            ((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id)) & (Fixture.played == True)
        ).all()

        # Calculate statistics for each team
        for f in fixtures:
            if f.home_team_id == team.id:
                gf += f.home_goals
                ga += f.away_goals
                played += 1
                if f.home_goals > f.away_goals: won += 1; pts += 3
                elif f.home_goals == f.away_goals: drawn += 1; pts += 1
                else: lost += 1
            elif f.away_team_id == team.id:
                gf += f.away_goals
                ga += f.home_goals
                played += 1
                if f.away_goals > f.home_goals: won += 1; pts += 3
                elif f.away_goals == f.home_goals: drawn += 1; pts += 1
                else: lost += 1

        # Append team statistics to table_data list
        table_data.append({
            'team': team.name,
            'played': played,
            'won': won,
            'drawn': drawn,
            'lost': lost,
            'gf': gf,
            'ga': ga,
            'gd': gf - ga,
            'points': pts
        })

    # Sort table_data list by points and goal difference in descending order
    table_data.sort(key=lambda x: (x['points'], x['gd']), reverse=True)

    # Retrieve upcoming fixtures and results
    upcoming = Fixture.query.filter_by(played=False).order_by(Fixture.fixture_time.asc()).all()
    results = Fixture.query.filter_by(played=True).order_by(Fixture.fixture_time.desc()).all()

    # Render index.html template with table_data, upcoming, and results
    return render_template('index.html', table=table_data, upcoming=upcoming, results=results)

@app.route('/add_team', methods=['POST'])
@admin_required
def add_team():
    # Handle POST request to add a new team
    name = request.form['team_name']
    if name and not Team.query.filter_by(name=name).first():
        new_team = Team(name=name)
        db.session.add(new_team)
        db.session.commit()

        # Auto-generate fixtures against existing teams
        existing_teams = Team.query.filter(Team.id != new_team.id).all()
        for team in existing_teams:
            db.session.add(Fixture(home_team_id=team.id, away_team_id=new_team.id))
            db.session.add(Fixture(home_team_id=new_team.id, away_team_id=team.id))
        db.session.commit()

    # Redirect to index page after adding a team
    return redirect(url_for('index'))

@app.route('/update_fixture_datetime', methods=['POST'])
@login_required
def update_fixture_datetime():
    fixture_id = request.form.get('fixture_id')
    fixture_date = request.form.get('fixture_date')  # Expected format: "YYYY-MM-DDTHH:MM"
    if fixture_id and fixture_date:
        from datetime import datetime
        try:
            fixture = Fixture.query.get(int(fixture_id))
            if fixture and (not fixture.played) and fixture.home_goals is None and fixture.away_goals is None:
                fixture.fixture_time = datetime.strptime(fixture_date, '%Y-%m-%dT%H:%M')
                db.session.commit()
        except Exception as e:
            # Handle conversion or database errors as needed
            print(e)
    return redirect(url_for('index'))


if __name__ == '__main__':
    # Run the Flask application
    app.run(debug=True, host="0.0.0.0", port=5000)
