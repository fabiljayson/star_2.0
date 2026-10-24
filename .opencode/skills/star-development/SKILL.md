---
name: star-development
description: STAR surgical platform work — use for ANY task in the star repo (Django backend, React web, Flutter mobile). Covers test/seed/run commands, API error envelope, milestone workflow and documented pitfalls. Use ALWAYS when cwd is or files are under /home/fabiljayson/Projects/star.
---

# STAR development playbook

STAR = surgical platform (logbook, training, marketplace, legal) with three apps in one repo:
backend (Django 6.1 + DRF, port **8002**), web (React 19 + Vite, port **5174**), mobile (Flutter via fvm).

## Non-negotiables

- Work **milestone by milestone, validated by the user** before moving on. Commit after each delivered step.
- UI copy in **English**. Code comments English.
- Design system = `DESIGN.md` (web: teal `#00adb5` tokens in `web/src/styles/`; mobile: `lib/theme.dart` + Atkinson Hyperlegible).
- Audit log is append-only. Private file storage has **no public URL** (`storage.url()` raising ValueError is intentional — use the auth'd download endpoint).
- API errors use the envelope `{"error": {code, message, details}}` — assert via helper `error_details(response)`.

## Commands (Run from the app dir)

Backend (`star/backend/`, venv via uv):
```bash
uv run pytest                      # note: -q already in addopts; a second -q = -qq (no summary)
uv run ruff check .
uv run python manage.py runserver 0.0.0.0:8002
uv run python manage.py seed_demo          # demo accounts, password Demo!Passw0rd2026 (admin password is randomized)
uv run python manage.py seed_showcase --force  # big showcase dataset
uv run python manage.py expire_marketplace_orders  # cron-style TTL cleanup
uv run python manage.py makemigrations --check --dry-run
docker compose up -d               # Postgres 16 on 5433
```
Web (`star/web/`): `npm run dev` (5174, `/api` proxied to 8002), tests = vitest, lint = `npx oxlint src` (no `npm run lint` script).
Mobile (`star/mobile/`, Flutter via **fvm**): `fvm flutter analyze|test|run`, `fvm dart analyze` from `mobile/` only.

## Documented pitfalls (do not rediscover)

- Multipart uploads with DRF `APIClient` need `format="multipart"` (JSON is the default).
- `Model.save()` does not run `full_clean()` — validate in serializers.
- Do not wrap in `@transaction.atomic` a function that must persist a FAILED job status.
- DRF: `DEFAULT_THROTTLE_RATES` (not `THROTTLE_RATES`); settings under `SIMPLE_JWT` key.
- A 401 from a blacklisted refresh token returns `InvalidToken`, not a generic 400.
- Custom exceptions expose `default_code` in `core/exceptions.py` — the handler reads that, not DRF detail code.
- pytest-django: use `django.test.override_settings`, never a `pytest.settings` attribute.
- Migrations: always `makemigrations <app>` explicitly; a new app without migrations gets created out of order via `--run-syncdb`.
- `pkill -f` can match your own shell's command line — use character-class patterns (`runserver 0[.]0.0.0`).
- Any object mutated by another flow needs `refresh_from_db()` before asserting its status.

## Current status

Milestones 1–8 + M9a (legal backend, commit `075501f`) are delivered and committé. Next: **M9b** (web Policy Center pages, consent UI, bilingual EN/FR) then **M9c** (mobile settings + consent, refetch on resume).
