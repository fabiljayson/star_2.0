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
                    │  │ apps.logbook     surgical records,   │  │
                    │  │                 lifecycle, files     │  │
                    │  │ apps.training    placements,         │  │
                    │  │                 competencies, scores │  │
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

### Domain model (Milestone 2 — surgical logbook, `apps.logbook`)

- **`PatientReference`** — random `PR-XXXXXXXX` code, unique *per
  institution*, generated with `secrets` (never derived from identifiers).
  STAR stores **no** re-identification mapping: the authoritative link stays
  in the hospital's own record system.
- **`SurgicalProcedure`** — unique human reference `STAR-YYYY-XXXXXX`,
  institution/department/specialty scope, pseudonymous patient reference,
  clinical note fields (indication, summary, complications, postoperative,
  training objectives), lifecycle status, author, `version` counter.
- **`ProcedureParticipant`** — user + role (primary operator / assistant /
  observer), unique per record; the author is never a participant row.
- **`ProcedureNoteVersion`** — immutable JSON snapshot of the note fields,
  taken at submission and at every post-approval correction (sequenced per
  record).
- **`ReviewDecision`** — reviewer, decision (start review / approve /
  request correction / reject), from→to status, mandatory reason for
  non-approvals, record version reviewed.
- **`Attachment`** — private-storage file with original name, *detected*
  content kind, size, SHA-256, uploader. Binaries never live in relational
  tables.

#### Education model (Milestone 3a — `apps.training`)

- **`TrainingPlacement`** — trainee ↔ institution/department/period with
  supervisor, objectives and expected competencies; statuses
  `active → completed|cancelled`; **one active placement per trainee**
  (partial unique constraint at the database level).
- **`ExaminerAssignment`** — explicit examiner authorization per placement
  (unique per pair); the examiner role alone grants no assessment rights.
- **`Competency`** — institution-scoped catalog (unique `code` per
  institution).
- **`CompetencyRubricVersion`** — immutable JSON rubric snapshot
  (`scale` + `criteria`), auto-numbered; only the latest is `is_current`.
- **`Assessment`** — assessor + placement + competency + pinned rubric
  version, criterion scores, overall level, feedback; statuses
  `draft → submitted → approved | needs_correction | rejected`
  (`needs_correction` loops back to the assessor).

Education rules enforced in `apps/training/services.py`:

- Placements are managed by institution supervisors, department managers
  and institution administrators; trainees may only read their own.
- Assessments are created by the placement supervisor, assigned examiners
  or managers — and decided by **someone else** (self-approval impossible);
  corrections/rejections require a reason.
- Scores are validated against the pinned rubric (unknown criteria or
  levels are rejected), and procedure counts stay separate from
  qualitative ratings (a count never marks a competency as achieved).
- Out-of-scope education records return `404`, consistent with the
  clinical API.

#### Record lifecycle

```
draft ──submit──▶ submitted ──start_review──▶ under_review
  ▲                  │  │                          │
  │                  │  └────── approve ───────────┤
  │                  └──── approve/return ─────────┤
  │                                                ▼
  └───── edit (author) ◀── return (reason) ◀── approved ──archive──▶ archived
                              │                    │
                              └── resubmit ────────┘   (edit ⇒ new note
                                                         version + re-review)
```

Rules enforced in `apps/logbook/services.py`:

- Only the **author** edits/submits; only institution
  **supervisor/examiner/admin** reviews; reviewers never review their own
  records (no self-approval).
- `request_correction` / `reject` require a reason; invalid transitions
  return `400`, out-of-scope records return `404` (existence never leaks).
- Editing an **approved** record stores the approved content as a note
  version, bumps `version`, and returns the record to `submitted`.
- Archived records are read-only.
- Visibility: author + participants + institution-wide roles
  (supervisor/examiner/manager/admin). Platform administrators and
  supplier/buyer accounts see **nothing** clinical by default; independent
  surgeons may create in any institution but read only their own records.

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
- **Mock boundaries:** external integrations (payments, transcription) are
  abstracted with clearly labelled sandbox/mock providers; simulated
  results are never presented as real ones (M3 transcription shipped as a
  mock, payments planned for M5).

## 7. Milestone status

- **M1 (done):** repository layout, Dockerized PostgreSQL, settings modules,
  JWT auth + MFA + recovery, roles/memberships/invitations, institutions and
  departments, audit trail, OpenAPI docs, health check, 54 automated tests,
  CI workflow.
- **M2 (done):** `apps.logbook` — pseudonymous patient references, surgical
  records with lifecycle state machine, participants, submission/review/
  approval/return/archive actions, post-approval versioning, private
  attachment storage with content sniffing and permission-checked download,
  institution-scoped visibility (404 out of scope), demo seed, 52 new tests
  (106 total).
- **M3a (done):** `apps.training` — placements with lifecycle + one-active-
  per-trainee constraint, explicit examiner assignments, institution
  competency catalog, immutable rubric versions, assessment workflow
  (no self-approval, mandatory reasons), placement progress endpoint
  (logbook counts + competency state), demo seed, 64 new tests (170 total).
- **M3b (done):** transcription adapter behind a provider interface
  (`MockTranscriptionProvider`, deterministic output in `en`/`fr`, results
  labelled `simulated`, audio validated and discarded, outage toggle
  `TRANSCRIPTION_MOCK_FAILURE` → 503) plus an in-app notification centre
  (`apps.notifications`): 8 categories, preferences per user/category, recipient
  isolation, generic previews that never contain clinical text; triggers wired
  into submission/review, placements, examiner assignments and assessment
  submit/decide. 33 new tests (203 total).
- **M4a (done):** `apps.reports` — `ReportJob` (requester + status + artifact with
  TTL), 4 logbook reports (individual logbook, activity by date range, activity
  by specialty and institution, procedures by participation role), CSV (UTF-8
  BOM, OWASP formula-injection guard) and PDF (WeasyPrint) rendering, synchronous
  generation with a configurable row limit, expiring download links (410), audit
  trail (`report.requested/downloaded/failed`), exports reuse the logbook
  row-level visibility filter so a report can never contain records its requester
  could not see, and never expose patient reference codes — 23 new tests
  (226 total).
- **M4b (planned):** training reports (trainee progress, competency assessments,
  examiner reviews, placement completion, institution aggregates).
- **M5–M7:** per README milestones.
