# League Simple

Small Flask app for running a football league table with fixtures, results, users, and admin controls.

## Features

- Server-rendered league table with live standings
- Upcoming fixtures and recorded results
- Login-protected app with admin and non-admin users
- Admin tools for teams, fixtures, users, and league reset
- Render-ready deployment via `render.yaml`

## Stack

- Python 3.12
- Flask
- Flask-SQLAlchemy
- PostgreSQL via `psycopg`
- Gunicorn for production
- Jinja templates for UI

## Project Structure

- `app.py` - app setup, config, home page, standings, fixture score updates
- `auth.py` - login/logout and admin bootstrap user creation
- `admin.py` - admin panel routes for users, teams, fixtures, and reset
- `models.py` - SQLAlchemy models
- `templates/` - UI templates and shared styles
- `render.yaml` - Render service and database config
- `runtime.txt` - pinned Python version for Render
- `AGENTS.md` - coding-agent guidance for this repository

## Requirements

- Python 3.12.x
- PostgreSQL database
- `DATABASE_URL` environment variable

Python version is pinned in `runtime.txt` for Render deployments.

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local env file:

```bash
cp .env.example .env
```

## Environment Variables

### Required locally

- `DATABASE_URL`

### Required in production

- `DATABASE_URL`
- `SECRET_KEY`
- `LEAGUE_ADMIN_USERNAME`
- `LEAGUE_ADMIN_PASSWORD`

Notes:

- The app normalizes `postgres://` and `postgresql://` URLs to `postgresql+psycopg://` automatically.
- On startup, the app runs `db.create_all()` and ensures that at least one admin user exists.
- In non-production development only, the app can fall back to a default secret key and default admin credentials.

## Running Locally

Start the dev server:

```bash
python app.py
```

The app automatically loads variables from `.env` in the project root.

Open:

```text
http://127.0.0.1:5000
```

## Production-Style Run

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME \
SECRET_KEY=change-me \
LEAGUE_ADMIN_USERNAME=admin \
LEAGUE_ADMIN_PASSWORD=strong-password \
FLASK_ENV=production \
gunicorn app:app
```

## Validation Commands

There is no formal lint or test suite yet. Use these checks instead:

### Python syntax

```bash
python -m py_compile app.py admin.py auth.py models.py
```

### Template parse check

```bash
python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('templates')); [env.get_template(name) for name in ['index.html','admin.html','login.html','_theme_head.html']]; print('templates ok')"
```

### Dependency install check

```bash
pip install -r requirements.txt
```

## Tests

There is currently no `tests/` directory and no configured `pytest` suite.

If you add tests later, recommended single-test patterns are:

```bash
pytest tests/test_file.py::test_name
pytest tests/test_file.py::TestClass::test_name
```

## Render Deployment

This repo includes a `render.yaml` that defines:

- one Python web service
- one PostgreSQL database
- build command: `pip install -r requirements.txt`
- start command: `gunicorn app:app`

### Deploy on Render

1. Push this repository to GitHub.
2. In Render, create a new Blueprint instance from the repository.
3. Render will read `render.yaml` and provision the web service and database.
4. Set values for:
   - `LEAGUE_ADMIN_USERNAME`
   - `LEAGUE_ADMIN_PASSWORD`
5. `SECRET_KEY` is generated automatically by Render from `render.yaml`.

### Important deployment notes

- Boot requires a working database connection because `db.create_all()` runs on startup.
- Production startup fails fast if `SECRET_KEY` is missing.
- Production startup also fails if `LEAGUE_ADMIN_USERNAME` or `LEAGUE_ADMIN_PASSWORD` is missing and no admin user exists yet.

## Auth and Permissions

- All app pages require login.
- Non-admin users can view standings, enter fixture scores, and reschedule unplayed fixtures.
- Admin users can additionally manage teams, fixtures, users, and reset the league.

## UI Notes

- Shared UI styles live in `templates/_theme_head.html`.
- The app is designed for both desktop and mobile.
- Login is intentionally simple; home and admin pages carry the richer dashboard layout.

## Development Notes

- Keep changes minimal and aligned with the existing simple Flask style.
- Prefer updating shared template styles instead of adding one-off UI rules.
- If you add tools, tests, or deployment steps, update both `README.md` and `AGENTS.md`.
- Agent-specific repository guidance lives in `AGENTS.md`.
