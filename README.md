# STAR

**Secure Surgical Tracking, Assessment & Resources Platform**

STAR is a professional digital platform for documenting surgical procedures,
tracking clinical training experience, managing assessments, generating
reports, and purchasing surgical equipment from verified suppliers.

STAR is a documentation, education and commerce platform. It does **not**
diagnose patients, prescribe treatment, or replace an institution's official
medical record system.

> **Status:** Milestones 1–4 delivered (foundations, surgical logbook,
> education, mock transcription, in-app notifications and reports/exports).
> Milestone 5 (marketplace) is next.
> See [Milestones](#milestones).

---

## Contents

- [Architecture at a glance](#architecture-at-a-glance)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Running the test suite](#running-the-test-suite)
- [API](#api)
- [Ports](#ports)
- [Demo data](#demo-data)
- [Repository layout](#repository-layout)
- [Milestones](#milestones)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)

---

## Architecture at a glance

| Layer     | Technology |
|-----------|------------|
| Backend   | Python 3.14, Django 6.1, Django REST Framework 3.18, PostgreSQL 16 |
| Auth      | JWT (simplejwt) with refresh rotation, blacklist, `auth_version` revocation, optional TOTP MFA |
| API docs  | OpenAPI via drf-spectacular (`/api/v1/docs/`) |
| Web app   | React + Vite + TypeScript (planned, Milestone 6) |
| Mobile    | Flutter (planned, after the web app) |
| Tooling   | uv (Python), npm (web), Docker Compose (PostgreSQL), ruff, pytest |

**Domain apps** (backend):

- `apps.core` — audit trail, error format, pagination, permissions, health.
- `apps.accounts` — users, roles, JWT auth, MFA, recovery, invitations.
- `apps.organizations` — institutions, departments, specialties, memberships.
- `apps.logbook` — pseudonymous patient references, surgical records,
  participants, review lifecycle, note versioning, private attachments.
- `apps.training` — training placements, examiner assignments, competency
  catalog with immutable rubric versions, competency assessments, progress.

---

## Prerequisites

- Python **3.14** and [uv](https://docs.astral.sh/uv/)
- Docker with the Compose plugin (for PostgreSQL)
- Node.js 20+ and npm (needed from Milestone 6 onwards)
- Git

---

## Quick start

```bash
# 1. Environment file (edit the secrets for anything beyond local dev)
cp .env.example .env

# 2. Start PostgreSQL (port 5433)
docker compose up -d

# 3. Install Python dependencies
cd backend
uv sync

# 4. Create and apply the database schema
uv run python manage.py migrate

# 5. (Optional) synthetic demonstration data
uv run python manage.py seed_demo

# 6. Run the API on port 8002
uv run python manage.py runserver 0.0.0.0:8002
```

Then open:

- API docs (Swagger UI): <http://localhost:8002/api/v1/docs/>
- OpenAPI schema: <http://localhost:8002/api/v1/schema/>
- Health check: <http://localhost:8002/api/v1/health/>

Create your own platform administrator instead of relying on demo data:

```bash
uv run python manage.py createsuperuser
```

`createsuperuser` asks for an email and password; the account is created with
platform-administrator rights (`is_platform_admin`, staff access to
`/admin/`).

---

## Running the test suite

```bash
cd backend
uv run pytest          # 170 tests (Milestones 1–2 + training/M3)
uv run ruff check .    # lint
uv run python manage.py makemigrations --check --dry-run   # migrations up to date?
```

Tests run against a dedicated `test_star` PostgreSQL database
(pytest-django creates and destroys it) and never touch real services:
email uses the in-memory backend, external integrations are mocked.

---

## API

All endpoints live under `/api/v1/`. Conventions:

- **Authentication:** `Authorization: Bearer <access token>`
  (obtain tokens at `POST /api/v1/auth/login/`).
- **Pagination:** `{"count", "next", "previous", "results"}` with
  `?page=` / `?page_size=` (max 100).
- **Errors:** a uniform envelope:

  ```json
  {
    "error": {
      "code": "validation_error",
      "message": "Invalid input.",
      "details": {"email": ["An account with this email already exists."]}
    }
  }
  ```

- **Request id:** every response carries `X-Request-ID` (also logged).

Endpoint groups implemented in Milestone 1:

| Group | Examples |
|-------|----------|
| Auth | `POST /api/v1/auth/register/`, `login/`, `token/refresh/`, `logout/`, `logout-all/`, `password/forgot/`, `password/reset/`, `verify/`, `mfa/setup|enable|disable|verify/` |
| Users | `GET|PATCH /api/v1/users/me/`, `GET /api/v1/users/` (institution-scoped) |
| Organizations | `/api/v1/institutions/`, `/departments/`, `/specialties/`, `/memberships/`, `/invitations/` (+ `accept/`, `revoke/`) |
| Audit | `GET /api/v1/audit/` (platform or institution administrators) |
| Patient references | `GET|POST /api/v1/patients/references/`, `GET|PATCH .../{id}/` |
| Surgical records | `GET|POST /api/v1/procedures/`, `GET|PATCH .../{id}/` |
| Record actions | `POST .../{id}/submit/`, `GET|POST .../{id}/reviews/`, `POST .../{id}/archive/`, `GET .../{id}/versions/` |
| Participants | `GET|POST .../{id}/participants/`, `DELETE .../{id}/participants/{pid}/` |
| Attachments | `GET|POST .../{id}/attachments/`, `DELETE .../{id}/attachments/{aid}/`, `GET .../{id}/attachments/{aid}/download/` |
| Placements | `GET|POST /api/v1/training/placements/`, `GET|PATCH .../{id}/`, `POST .../{id}/complete/`, `.../cancel/`, `GET .../{id}/progress/` |
| Examiner assignments | `GET|POST .../{id}/examiners/`, `DELETE .../{id}/examiners/{aid}/` |
| Competencies | `GET|POST /api/v1/competencies/`, `GET|PATCH .../{id}/` |
| Rubric versions | `GET|POST .../{id}/rubric-versions/`, `GET .../{id}/rubric-versions/{vid}/` |
| Assessments | `GET|POST /api/v1/assessments/`, `GET|PATCH .../{id}/`, `POST .../{id}/submit/`, `POST .../{id}/decide/` |
| Transcription | `POST /api/v1/procedures/{id}/transcribe/` (author only, deterministic mock, audio never stored) |
| Notifications | `GET /api/v1/notifications/`, `GET .../unread-count/`, `POST .../read/`, `POST .../read-all/`, `GET|PUT|PATCH .../preferences/` |
| Reports | `GET|POST /api/v1/reports/`, `GET .../{id}/`, `GET .../{id}/download/` (CSV/PDF, links expire) |
| Ops | `GET /api/v1/health/`, `/schema/`, `/docs/` |

---

## Ports

| Service    | Port |
|------------|------|
| Django API | 8002 |
| PostgreSQL | 5433 |
| Web (Vite, future) | 5174 |

---

## Demo data

`uv run python manage.py seed_demo` creates **synthetic** institutions
(prefixed "Demo"), fictional accounts (all `@demo.test` addresses), a global
specialty catalog, three fictional surgical records (draft / submitted /
approved) with pseudonymous `PR-…` patient references, plus a synthetic
training placement, competency catalog and assessments. No real people,
institutions or patient data are ever included.

- Shared demo password (development only): `Demo!Passw0rd2026`
- The seed prints a random password for `platform-admin@demo.test` on first
  run — store it safely; it is shown only once.

Never seed demo data into a production environment.

---

## Repository layout

```
star/
├── backend/                 # Django project (uv, port 8002)
│   ├── config/settings/     # base / development / testing / production
│   ├── apps/core/           # audit, permissions, errors, pagination, health
│   ├── apps/accounts/       # users, roles, JWT, MFA, recovery, invitations
│   ├── apps/organizations/  # institutions, departments, specialties
│   ├── apps/logbook/        # surgical records, lifecycle, attachments
│   ├── apps/training/       # placements, competencies, assessments
│   └── conftest.py          # shared pytest fixtures
├── web/                     # React + Vite app (Milestone 6)
├── docs/                    # architecture, requirements, security, ...
├── docker-compose.yml       # PostgreSQL 16 (port 5433)
├── .env.example             # every environment variable, safe placeholders
└── .github/workflows/ci.yml # lint + tests on every push/PR
```

---

## Milestones

| # | Scope | Status |
|---|-------|--------|
| 1 | Foundations: structure, database, auth, roles, institutions, audit, CI | **done** |
| 2 | Surgical logbook: records, participants, lifecycle, attachments | **done** |
| 3 | Voice transcription adapter, training placements, competencies, assessments, notifications | **done** (203 tests) |
| 4 | Reports and exports (PDF/CSV) | **done** (9 report types, 245 tests) |
| 5 | Marketplace: suppliers, inventory, orders, sandbox payments | planned |
| 6 | Complete web (and mobile) interfaces | planned |
| 7 | Tests for scenarios A–H, security checks, deployment docs | planned |

See `docs/architecture.md` for design decisions and security notes.

---

## Security notes

- Passwords use Django's default PBKDF2 hasher with strong validators.
- JWT access tokens are short-lived (15 min default); refresh tokens rotate
  and are blacklisted on logout.
- `User.auth_version` revokes **all** outstanding tokens at once (logout
  everywhere, password reset, account disable).
- Institution-scoped roles are enforced server-side on every protected
  endpoint; cross-institution reads return `403` without leaking content.
- Clinical records return `404` (never `403`) outside the caller's scope, so
  record existence itself is not disclosed; platform administrators and
  marketplace (supplier/buyer) accounts have **no** clinical access by default.
- Surgical records cannot be edited while submitted/under review/archived;
  post-approval edits create an immutable note version and force re-review.
- Training data is institution-scoped like clinical data: trainees see their
  own placements, supervisors/managers their institution's, examiners only
  placements they are explicitly assigned to. A trainee can hold at most one
  active placement.
- Competency rubric versions are immutable snapshots; assessments pin the
  version they were scored against, so rubric changes never rewrite history.
  Assessments are always decided by someone other than their assessor (no
  self-approval), with a mandatory reason for corrections and rejections.
- Attachments are stored outside the web root in private storage; downloads
  require a JWT and permission check, with `Cache-Control: private, no-store`.
  Uploads are validated by size, extension allowlist **and** magic-byte
  content sniffing (filenames/MIME types are never trusted).
- Login, registration, password and MFA endpoints are rate-limited.
- Audit events are append-only through the API (no create/update endpoints).
- Optional TOTP second factor; `REQUIRE_MFA_FOR_PLATFORM_ADMINS=true` blocks
  privileged actions until MFA is enabled.
- Secrets come from the environment (`.env` is git-ignored). Never commit
  real credentials.

Technical controls alone do **not** make STAR legally compliant: a separate
legal, institutional and contractual review is required before any
production deployment involving real patient or trainee data.

---

## Troubleshooting

**`django.core.exceptions.ImproperlyConfigured: Deprecated email settings are not allowed when MAILERS is defined`**
You mixed old `EMAIL_HOST`-style settings with the new `MAILERS` dict. Use
`MAILERS` only (see `config/settings/base.py`).

**Port 5433 already in use**
Change `POSTGRES_PORT` in `.env` and `docker compose up -d` again.

**Tests fail to connect to the database**
PostgreSQL must be running: `docker compose up -d`. pytest-django uses a
separate `test_star` database on the same server.

**`uv run: command not found` / wrong Python**
Install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`), then run
`uv sync` inside `backend/`.

**Forgot the demo admin password**
Re-run the seed with an explicit password:
`uv run python manage.py seed_demo --admin-password 'YourNewPassword'`.
