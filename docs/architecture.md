# STAR — Architecture

This document records the architecture and the decisions taken while building
STAR. It is updated at every milestone.

## 1. System overview

```
                    ┌──────────────────────────────┐
   Browser (M6) ───▶│  React + Vite web app :5174  │──┐
                    └──────────────────────────────┘  │  (Vite proxy /api → :8002
                    ┌──────────────────────────────┐  │   or strict CORS allow-list)
   Flutter (M6+) ──▶│  Mobile app                   │──┤
                    └──────────────────────────────┘  │
                                                      ▼
                    ┌───────────────────────────────────────────┐
                    │  Django REST API  (config.settings.*)     │
                    │  /api/v1/…                :8002           │
                    │  ┌─────────────────────────────────────┐  │
                    │  │ apps.core       audit, permissions, │  │
                    │  │                 errors, health      │  │
                    │  │ apps.accounts   users, roles, JWT,  │  │
                    │  │                 MFA, recovery       │  │
                    │  │ apps.organizations institutions,    │  │
                    │  │                 departments, invites │  │
                    │  └─────────────────────────────────────┘  │
                    └───────────────┬───────────────────────────┘
                                    │
                     PostgreSQL 16 (:5433)   private media volume (M2)
```

One backend serves every client. All authorization is enforced **server-side**;
clients only render what the API returns.

## 2. Technology choices

| Decision | Choice | Why |
|----------|--------|-----|
| Language/runtime | Python 3.14, Django 6.1 | Current stable Django line supporting Python 3.14. |
| API framework | DRF 3.18 | Mature permission/filter/pagination ecosystem. |
| Database | PostgreSQL 16 in Docker | Same engine in dev, test and production; constraints, JSONB, row locks for inventory (M5). |
| Auth | JWT (simplejwt), refresh rotation + blacklist | Stateless for mobile/web, revocable via `auth_version`; no long-lived secrets in storage. |
| API docs | drf-spectacular (OpenAPI 3) | Generated from the code, always in sync. |
| Env config | `python-dotenv` + typed helpers | Plain `.env` files, `.env.example` documents every variable. |
| Lint/tests | ruff, pytest + pytest-django | Fast feedback; factories for fixtures. |
| Package mgmt | uv (backend), npm (web) | Per `CLAUDE.md`/`AGENTS.md` conventions. |

### Settings modules

| Module | Use |
|--------|-----|
| `config.settings.base` | Shared configuration, environment parsing. |
| `config.settings.development` | Local dev: debug on, console email, permissive hosts. |
| `config.settings.testing` | pytest: fast hashers, locmem email, dummy cache. |
| `config.settings.production` | Requires real secrets, HTTPS cookies, HSTS. |

## 3. Domain model (Milestone 1)

- **`accounts.User`** — UUID pk, unique email as login, `is_verified`,
  `is_platform_admin`, `auth_version` (global token revocation), TOTP MFA
  fields.
- **`accounts.RoleAssignment`** — the role/affiliation table. An
  institution-scoped role row *is* the user's membership in that institution
  (`institution` set, optional `department`). Platform roles
  (independent surgeon, buyer, supplier) keep `institution = NULL`.
  Platform administration is deliberately **not** a row: it is the audited
  `User.is_platform_admin` flag.
- **`organizations.Institution / Department / Specialty / Invitation`** —
  organizational structure plus invitation-based onboarding (single-use,
  expiring token, mailbox ownership proof).
- **`core.AuditEvent`** — append-only security/business trail with actor,
  action, object reference, institution scope, IP, user agent and request id.
  Never contains clinical text, passwords or payment data.

Data dictionary and ER diagram: `docs/data-dictionary.md` (Milestone 7).

## 4. Authentication & authorization

1. `POST /auth/login/` → short-lived access + rotating refresh (both carry
   the `auth_version` claim). MFA-enabled users first receive a 5-minute
   `mfa_token` and must verify a TOTP code.
2. Every request re-checks `user.is_active` **and** `auth_version`
   (`apps.accounts.authentication.JWTAuthentication`), so disabling an
   account or "logout everywhere" kills all outstanding tokens instantly.
3. Permissions are explicit per view:
   - `require_platform_admin(user)` — platform operations (+ optional MFA
     policy),
   - `require_institution_admin(user, institution)` — institution-scoped
     operations,
   - `require_role(user, role, institution)` — role checks,
   - queryset scoping in list endpoints (a URL guessing another
     institution's id returns `403`, never data).

## 5. API conventions

- Versioned prefix `/api/v1/`.
- Uniform error envelope `{"error": {code, message, details}}`
  (`apps.core.exceptions`), never leaking internals.
- Page-number pagination (20 default, max 100), django-filter filtersets,
  search/ordering on lists.
- Scoped throttles: `login`, `register`, `password`, `mfa`.
- `X-Request-ID` on every response, correlated with logs and audit rows.

## 6. Cross-cutting rules

- **Audit or fail:** `record_audit()` raises on persistence failure — an
  operation never succeeds without its audit row.
- **Soft deactivation** for memberships and departments so history and audit
  stay intact; hard deletion is reserved for data without retention value.
- **No secrets in code:** everything comes from the environment; `.env` is
  git-ignored.
- **Mock boundaries:** external integrations (payments, transcription) will
  be abstracted with clearly labelled sandbox/mock providers; simulated
  results are never presented as real ones (M3/M5).

## 7. Milestone status

- **M1 (done):** repository layout, Dockerized PostgreSQL, settings modules,
  JWT auth + MFA + recovery, roles/memberships/invitations, institutions and
  departments, audit trail, OpenAPI docs, health check, 54 automated tests,
  CI workflow.
- **M2–M7:** per README milestones.
