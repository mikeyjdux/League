# AGENTS.md

This file guides coding agents working in `/home/mduxbury/Footy/league_simple`.

## Project Overview

- Small Flask app for managing a football league table, fixtures, users, and admin actions.
- Server-rendered UI using Jinja templates in `templates/`.
- Data layer uses Flask-SQLAlchemy with PostgreSQL.
- Deployment target is Render via `render.yaml`.

## Repository Layout

- `app.py` - app bootstrap, config, main routes, standings computation.
- `auth.py` - login/logout, auth decorators, bootstrap admin user.
- `admin.py` - admin-only management routes.
- `models.py` - SQLAlchemy models.
- `templates/` - Jinja HTML templates and shared theme CSS.
- `requirements.txt` - runtime dependencies.
- `render.yaml` - Render service/database config.
- `runtime.txt` - pinned Python runtime for Render.
- `README.md` - human-facing setup and deployment guide.

## Existing Agent/Editor Rules

- No `.cursorrules` file exists.
- No `.cursor/rules/` directory exists.
- No `.github/copilot-instructions.md` file exists.
- This AGENTS.md is the primary agent instruction file in this repository.

## Environment Requirements

- Python runtime is pinned in `runtime.txt`.
- `DATABASE_URL` is required at startup.
- In production, `SECRET_KEY` is required.
- In production, `LEAGUE_ADMIN_USERNAME` and `LEAGUE_ADMIN_PASSWORD` are required.
- Render deployment uses `gunicorn app:app`.

## Setup Commands

- Create venv: `python -m venv .venv`
- Activate venv: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Reinstall after dependency changes: `pip install -r requirements.txt`

## Run Commands

- Local dev server: `DATABASE_URL=postgresql+psycopg://... python app.py`
- Production-style server: `DATABASE_URL=postgresql+psycopg://... SECRET_KEY=... gunicorn app:app`

## Build / Lint / Test Commands

There is no formal linting or test suite configured right now.

Use these validation commands instead:

- Python syntax check: `python -m py_compile app.py admin.py auth.py models.py`
- Template parse check:
  `python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('templates')); [env.get_template(name) for name in ['index.html','admin.html','login.html','_theme_head.html']]; print('templates ok')"`
- Dependency install check: `pip install -r requirements.txt`
- Render config sanity check: review `render.yaml` and ensure required env vars are set.

## Single-Test Guidance

- There is currently no `tests/` directory and no `pytest` config in this repo.
- Because no automated tests exist, there is no real single-test command today.
- If you add pytest later, use this convention for one test:
  `pytest tests/test_file.py::test_name`
- If you add a test class later, use:
  `pytest tests/test_file.py::TestClass::test_name`
- Do not document or assume pytest exists unless you add it in the same change.

## Deployment Notes

- Render web service and database are defined in `render.yaml`.
- `DATABASE_URL` from Render may arrive as `postgres://` or `postgresql://`; app code normalizes it to `postgresql+psycopg://`.
- Startup runs `db.create_all()` automatically, so boot requires a working database connection.
- Do not remove the production env checks unless explicitly requested.
- Keep `README.md` and this file in sync if deployment steps change.

## Code Style Guidelines

### General

- Follow the existing simple Flask style; prefer small modules and straightforward route handlers.
- Keep changes minimal and local unless a shared helper clearly reduces duplication.
- Preserve server-rendered Jinja patterns instead of introducing frontend frameworks.
- Use ASCII by default.

### Imports

- Group imports in this order: standard library, third-party, local modules.
- Keep one import per line when practical.
- Avoid unused imports.
- Prefer explicit imports over wildcard imports.

### Formatting

- Match the existing 4-space indentation style.
- Keep route handlers readable; avoid unnecessary nesting.
- Prefer short blocks and early returns where helpful.
- Preserve surrounding file style even if it is not perfect.
- Do not introduce a formatter-specific style that clashes with the current codebase.

### Naming

- Use `snake_case` for functions, variables, and module-level helpers.
- Use `PascalCase` for SQLAlchemy model classes.
- Use clear route/helper names like `update_fixture_datetime` rather than abbreviations.
- Template class names should stay descriptive and aligned with current naming patterns.

### Types

- The repo does not currently use type hints consistently.
- Do not add broad type-annotation churn just for style.
- Add targeted type hints only when they materially improve a new helper or reduce ambiguity.

### Flask / Route Conventions

- Keep decorators close to the function they protect.
- Use `@login_required` and `@admin_required` consistently for permission boundaries.
- Redirect back to the relevant page after POST actions unless there is a strong reason not to.
- Keep route behavior explicit; avoid hidden side effects.

### Database Conventions

- Use SQLAlchemy models from `models.py`.
- Commit only after a coherent unit of work is complete.
- Avoid partial writes where one half of a multi-step update can commit without the other.
- When changing fixture state, keep `played`, `home_goals`, and `away_goals` logically consistent.
- Be careful with destructive queries such as league resets and deletes.

### Error Handling

- Fail fast for missing required production configuration.
- For user-driven form actions, prefer safe guards plus redirect over uncaught exceptions.
- Do not silently swallow important failures.
- Avoid broad `except` unless there is a clear reason; if catching broadly, keep the block small and intentional.
- Prefer validation before mutation.

### Security / Auth

- Treat auth changes as high-risk.
- Keep server-side authorization checks even if the UI hides controls.
- Do not introduce insecure production fallbacks for secrets or admin credentials.
- Preserve password hashing via Werkzeug helpers.

### Templates / UI

- Reuse shared styles in `templates/_theme_head.html` instead of scattering one-off inline styles.
- Keep mobile behavior in mind when adding new layout classes.
- Avoid adding UI text that clutters compact cards unless it clearly improves usability.
- Match existing card, chip, button, and spacing patterns.

### Comments

- Keep comments sparse.
- Use comments only where logic is genuinely non-obvious.
- Avoid narrating obvious code.

## Change Management Guidance

- Before editing, inspect nearby code and match local conventions.
- If you change permissions or environment handling, verify the full flow, not just the template.
- If you add new commands or tooling, update this file.
- If you add tests, add the exact test and single-test commands here.

## Preferred Validation Before Finishing

- Run `python -m py_compile app.py admin.py auth.py models.py`
- Run the Jinja template parse check.
- If config changed, sanity-check startup assumptions against `render.yaml`.
- If UI changed, review both desktop and mobile-critical templates.
