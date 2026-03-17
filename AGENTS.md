# AGENTS.md

Guidance for coding agents working in `/home/mduxbury/Footy/league_simple`.

## Project Snapshot

- Flask app for managing football leagues, seasons, teams, fixtures, users, and roles.
- Server-rendered UI with Jinja templates in `templates/`.
- PostgreSQL-backed data model via Flask-SQLAlchemy.
- Production deploys are handled by GitHub Actions via a self-hosted runner.
- Current branding is `LeagueOn`.

## Key Files

- `app.py` - app bootstrap, env/config checks, dashboard routes, invite-join flow.
- `auth.py` - login, logout, registration, decorators, bootstrap admin creation.
- `admin.py` - global admin routes and league manager routes.
- `league.py` - join code helpers, league context loading, schema patch helpers.
- `models.py` - SQLAlchemy models.
- `templates/index.html` - main dashboard.
- `templates/admin.html` - league manager UI.
- `templates/admin_overview.html` - global admin UI.
- `templates/login.html` - login and registration UI.
- `templates/_theme_head.html` - shared theme and component styles.
- `README.md` - user-facing setup and deployment notes.
- `.github/workflows/deploy.yml` - production deploy workflow.
- `scripts/deploy_leagueon.sh` - server-side deploy script.

## Existing Agent / Editor Rules

- No `.cursorrules` file exists.
- No `.cursor/rules/` directory exists.
- No `.github/copilot-instructions.md` file exists.
- This file is the canonical in-repo instruction source for coding agents.

## Environment Expectations

- Python version is pinned in `runtime.txt`.
- `DATABASE_URL` is required at startup.
- Production requires `SECRET_KEY`.
- Production bootstrap may require `LEAGUE_ADMIN_USERNAME` and `LEAGUE_ADMIN_PASSWORD`.
- The app expects PostgreSQL and normalizes `postgres://` and `postgresql://` URLs to `postgresql+psycopg://`.
- The app calls `db.create_all()` during startup; a working database connection is required to boot.

## Setup Commands

- Create virtualenv: `python -m venv .venv`
- Activate virtualenv: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Reinstall after dependency changes: `pip install -r requirements.txt`

## Run Commands

- Local dev server:
  `export DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME && python app.py`
- Production-style local run:
  `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME SECRET_KEY=change-me LEAGUE_ADMIN_USERNAME=admin LEAGUE_ADMIN_PASSWORD=strong-password FLASK_ENV=production gunicorn app:app`

## Build / Lint / Test Commands

There is no formal lint configuration and no committed automated test suite right now.

Use these validation commands before finishing non-trivial changes:

- Python syntax check:
  `python -m py_compile app.py admin.py auth.py models.py league.py`
- Template parse check:
  `python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('templates')); [env.get_template(name) for name in ['index.html','admin.html','login.html','_theme_head.html','_csrf_token.html','admin_overview.html']]; print('templates ok')"`
- Dependency install sanity check:
  `pip install -r requirements.txt`

## Single-Test Guidance

- There is currently no `tests/` directory.
- There is currently no configured `pytest` suite.
- Because no automated tests exist, there is no real single-test command today.
- If you add `pytest`, use these exact single-test patterns:
  - `pytest tests/test_file.py::test_name`
  - `pytest tests/test_file.py::TestClass::test_name`
- If you add tests in a change, update this file with the real commands you introduced.

## Deployment Notes

- Deploy target is a Linux server with a self-hosted GitHub Actions runner.
- GitHub Actions triggers production deploys on pushes to `main`.
- The production app lives at `/opt/leagueon/app`.
- The production systemd service is `leagueon.service`.
- The server-side deploy script lives at `/opt/leagueon/bin/deploy-leagueon` and is sourced from `scripts/deploy_leagueon.sh` in the repo.
- Do not remove production env guards unless explicitly asked.
- Keep deployment documentation aligned between `README.md` and this file.

## Architecture Notes

- `User.is_admin` is the global admin flag.
- `LeagueMembership.role` is league-scoped and currently uses `user` or `moderator`.
- League access is enforced server-side through `login_required`, `admin_required`, and `load_league_context()`.
- Invite links should support both logged-in and logged-out users.
- Invalid league access typically redirects through the app's 404 handling rather than showing a raw not-found page.
- Schema compatibility is maintained in `league.py` through startup patch helpers rather than a formal migration system.

## Code Style Guidelines

### General

- Keep the code simple and explicit; this repo favors straightforward Flask patterns over abstraction-heavy architecture.
- Prefer small helpers when they remove clear duplication, but avoid introducing frameworks or large service layers.
- Match existing structure and naming in the file you are editing.
- Use ASCII by default.

### Imports

- Order imports as: standard library, third-party, local modules.
- Keep imports explicit; do not use wildcard imports.
- Remove unused imports when touching a file.
- Prefer one logical import line per source unless a grouped import is already clearer and matches local style.

### Formatting

- Use 4-space indentation.
- Preserve the current style of short functions, direct control flow, and early returns.
- Keep route handlers readable; avoid deep nesting when a guard clause works.
- Do not introduce tool-specific formatting churn without need.

### Types

- The repository is not consistently type-annotated.
- Do not add broad type-hint churn to old files.
- Add targeted type hints only when writing new helpers where they materially improve clarity.

### Naming

- Use `snake_case` for functions, variables, routes, and helpers.
- Use `PascalCase` for SQLAlchemy model classes.
- Use descriptive names for route handlers, such as `join_league_from_link` rather than vague verbs.
- Keep template IDs and class names descriptive and aligned with existing UI naming.

### Flask Conventions

- Keep decorators immediately above the protected function.
- Use `@login_required` for authenticated routes and `@admin_required` for global admin routes.
- For league-scoped access, rely on `load_league_context()` instead of duplicating permission logic.
- Redirect after successful POST requests.
- Use `flash()` for user-visible outcomes when a form or invite action succeeds or fails.

### Database Conventions

- Use models and shared helpers from `models.py` and `league.py` rather than reimplementing queries ad hoc.
- Commit only after a coherent unit of work is complete.
- Keep fixture state logically consistent: if scores are present, `played` should match.
- Be cautious with delete operations; understand related memberships, teams, fixtures, and seasons first.
- Avoid schema changes that bypass the current compatibility helpers unless you are intentionally changing that approach.

### Error Handling

- Fail fast for missing required production configuration.
- For user-driven invalid input, prefer validation plus redirect/flash instead of uncaught exceptions.
- Catch narrow exception types where possible.
- Avoid broad `except Exception` blocks.
- Validate before mutating database state.

### Security and Auth

- Treat auth, role, and membership changes as sensitive.
- Keep authorization checks on the server even if the UI hides controls.
- Preserve password hashing through Werkzeug helpers.
- Do not add insecure production fallbacks for secrets or admin credentials.
- Be careful not to create routes that let users cross league boundaries without membership checks.

### Templates and UI

- Reuse shared styling patterns from `templates/_theme_head.html`.
- Keep the app server-rendered; do not add a frontend framework.
- Prefer compact, intentional UI copy over explanatory filler text.
- Maintain working mobile layouts when changing cards, tables, modals, and header actions.
- When changing invite/join flows, update both backend behavior and any copied/share link in the templates.

### Comments

- Keep comments sparse.
- Add comments only when a block is non-obvious.
- Do not narrate straightforward code.

## Change Management

- Read nearby code before editing and match local conventions.
- If you change env handling, auth, permissions, or deployment behavior, verify the full flow.
- If you add tooling, tests, or new validation commands, update this file.
- If you add editor-specific rules later, summarize them here too.

## Preferred Validation Before Finishing

- Run `python -m py_compile app.py admin.py auth.py models.py league.py`.
- Run the Jinja template parse check.
- If you changed templates, verify the affected page flow mentally for both desktop and mobile.
- If you changed auth, invites, or league access, verify both logged-in and logged-out paths.
- If you changed deployment config, cross-check the GitHub Actions workflow, the deploy script, and required environment variables.
