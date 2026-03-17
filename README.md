# LeagueOn

Small Flask app for running football leagues with standings, fixtures, league membership, and role-based admin controls.

## Features

- Multi-league support with per-league membership
- Active season per league
- Permanent 5-character league join codes
- Self-registration with a valid league code
- Global admin tools for leagues, users, and moderator assignment
- League moderator tools for teams and fixtures
- Server-rendered league table with upcoming fixtures and recorded results
- GitHub Actions deployment via a self-hosted runner on the production server

## Stack

- Python 3.12
- Flask
- Flask-SQLAlchemy
- PostgreSQL via `psycopg`
- Gunicorn for production
- Jinja templates for UI

## Project Structure

- `app.py` - app setup, config, dashboard routes, league joining, standings, fixture score updates
- `auth.py` - login/logout, registration, and bootstrap admin user creation
- `admin.py` - global admin routes and league management routes
- `league.py` - league helpers, join-code helpers, memberships, and context loading
- `models.py` - SQLAlchemy models for leagues, seasons, memberships, fixtures, and users
- `templates/` - UI templates and shared styles
- `.github/workflows/deploy.yml` - deploy workflow triggered by pushes to `main`
- `scripts/deploy_leagueon.sh` - server-side deploy script used by the workflow
- `runtime.txt` - pinned Python version
- `AGENTS.md` - coding-agent guidance for this repository

## Requirements

- Python 3.12.x
- PostgreSQL database
- `DATABASE_URL` environment variable

Python version is pinned in `runtime.txt`.

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
- For local development, export variables in your shell before starting the app.

## Running Locally

Start the dev server:

```bash
export DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME
python app.py
```

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
python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('templates')); [env.get_template(name) for name in ['index.html','admin.html','login.html','_theme_head.html','_csrf_token.html','admin_overview.html']]; print('templates ok')"
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

## Production Deployment

Production deploys are triggered automatically by GitHub Actions whenever `main` is updated.

### Production prerequisites

- The production server hosts the app at `/opt/leagueon/app`.
- `/opt/leagueon/app` is a git checkout of this repository.
- The Python virtualenv lives at `/opt/leagueon/app/.venv`.
- The systemd service is `leagueon.service`.
- A deploy script is installed on the server at `/opt/leagueon/bin/deploy-leagueon`.
- A self-hosted GitHub Actions runner is installed on the server, typically at `/opt/actions-runner`.

### Self-hosted runner setup

Create a dedicated runner user and install the GitHub Actions runner service on the production server:

```bash
sudo adduser --system --group --home /opt/actions-runner github-runner
sudo install -d -o github-runner -g github-runner /opt/actions-runner
```

Download the latest Linux ARM64 runner package from GitHub, extract it into `/opt/actions-runner`, and configure it against this repository as the `github-runner` user:

```bash
sudo -u github-runner bash
cd /opt/actions-runner
curl -L -o actions-runner.tar.gz https://github.com/actions/runner/releases/latest/download/actions-runner-linux-arm64-<version>.tar.gz
tar xzf actions-runner.tar.gz
./config.sh --url https://github.com/mikeyjdux/League --token <registration-token> --labels self-hosted,linux,arm64
exit
sudo /opt/actions-runner/svc.sh install github-runner
sudo /opt/actions-runner/svc.sh start
```

Generate the registration token from GitHub under `Settings` -> `Actions` -> `Runners` -> `New self-hosted runner`.

### Server deploy script install

Copy `scripts/deploy_leagueon.sh` to `/opt/leagueon/bin/deploy-leagueon` and make it executable:

```bash
sudo install -d -o leagueon -g leagueon /opt/leagueon/bin
sudo install -m 0755 scripts/deploy_leagueon.sh /opt/leagueon/bin/deploy-leagueon
```

The deploy user should be allowed to restart only `leagueon.service` with `sudo`.

The `github-runner` user should be allowed to execute the deploy script as `leagueon`:

```bash
echo 'github-runner ALL=(leagueon) NOPASSWD: /opt/leagueon/bin/deploy-leagueon' | sudo tee /etc/sudoers.d/github-runner-deploy >/dev/null
sudo chmod 440 /etc/sudoers.d/github-runner-deploy
sudo visudo -cf /etc/sudoers.d/github-runner-deploy
```

### What each deploy does

- fetches `origin/main`
- resets the production tree to match `origin/main`
- installs dependencies from `requirements.txt`
- runs Python syntax and Jinja template checks
- restarts `leagueon.service`

### Important production notes

- Boot requires a working database connection because `db.create_all()` runs on startup.
- Production startup fails fast if `SECRET_KEY` is missing.
- Production startup also fails if `LEAGUE_ADMIN_USERNAME` or `LEAGUE_ADMIN_PASSWORD` is missing and no admin user exists yet.
- Production deploys are deterministic because the server resets to `origin/main` on every run; do not make manual edits inside `/opt/leagueon/app`.
- The self-hosted runner only needs outbound internet access; the server does not need to be publicly reachable.

## Auth and Permissions

- All app pages require login.
- New users register with a valid league join code.
- Existing users can join additional leagues with a join code.
- Regular users can access only leagues they belong to.
- Moderators can manage teams and fixtures within their league.
- Global admins can manage all leagues, users, and moderator assignments.

## UI Notes

- Shared UI styles live in `templates/_theme_head.html`.
- The app is designed for both desktop and mobile.
- Login is intentionally simple; home and admin pages carry the richer dashboard layout.

## Development Notes

- Keep changes minimal and aligned with the existing simple Flask style.
- Prefer updating shared template styles instead of adding one-off UI rules.
- If you add tools, tests, or deployment steps, update both `README.md` and `AGENTS.md`.
- Agent-specific repository guidance lives in `AGENTS.md`.
