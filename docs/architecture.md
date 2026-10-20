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

#### Marketplace model (Milestone 5a — `apps.marketplace`)

- **Money:** integer amounts in XOF (ISO `XOF`, zero decimals) —
  `DecimalField(max_digits=12, decimal_places=0)`; currency stored on
  products and orders.
- **Supplier profile:** one per `SUPPLIER` account; starts `pending`,
  platform admin verifies (`verified`/`rejected`) or suspends with a reason.
  Only verified suppliers can sell; suspension blocks catalog management.
- **Product:** belongs to a supplier + category; SKU unique per supplier;
  `approval_status` (`pending` → `approved`/`rejected` by platform admin),
  `is_published`, `is_active`. Public catalog shows only
  approved + published products of verified suppliers.
- **Inventory:** `available_quantity` and `reserved_quantity` with a
  database CHECK (`reserved ≤ available`); `free_quantity` is a computed
  property; every change is an `InventoryMovement` row (restocked,
  reserved, released); no backorders — quantities are validated at cart
  and again under row locks at checkout.
- **Cart & checkout:** buyers only; checkout runs in one transaction with
  `select_for_update` on products, creates one `Order` per supplier
  (multi-supplier carts), snapshots line items (name, SKU, description,
  unit price, quantity), reserves stock, and clears the cart. Price or
  availability races surface as a 400 with per-item details.
- **Orders:** unique reference `ORD-YYYY-XXXXXX`, status machine
  (`pending_payment` → `paid` → `shipped` → `delivered`, plus `cancelled`
  and `refunded`), cancellation by buyer or platform admin releases
  reservations and logs movements; supplier sees its orders, buyer sees its
  own.
- **Sandbox payments (M5b):** `Payment` (one attempt per window; idempotency
  keys, amount/currency snapshots) + append-only `PaymentEvent` ledger. The
  **only** way money moves is a webhook signed with HMAC-SHA256 over the
  canonical JSON body (`PAYMENT_WEBHOOK_SECRET`, header
  `X-Payment-Signature`, constant-time compare); browser redirects and
  client-submitted statuses are never trusted. The sandbox `simulate`
  endpoint builds a real signed webhook and feeds the same handler, and only
  exists when `PAYMENTS_ACCEPT_MOCK` is true (forced `False` in
  `production.py`). Success consumes reservations into `sold` movements;
  refunds restock; pending windows auto-cancel via
  `expire_marketplace_orders` (TTL `PAYMENT_PENDING_TTL_HOURS`, default 24 h)
  which releases stock. Event payloads are redacted (no card/CVC keys) and
  full card data is never accepted or stored.
- **Fulfillment:** `Shipment` (shipped → delivered with tracking number,
  supplier-only), full-order `Refund` (buyer requests on a settled payment,
  supplier decides once; approval settles payment+order as refunded and
  restocks), `Dispute` (one per order, either party, text + file evidence in
  private storage with an authenticated download link; platform admin
  resolves — `buyer_favored` triggers the refund automatically,
  `supplier_favored` keeps the payment).
- **Isolation:** supplier/buyer roles have no clinical access
  (`MARKETPLACE_ONLY_ROLES` in `apps/logbook/services.py`).
- **Seller subscription (M8):** publishing requires, on top of the verified
  `SupplierProfile` flow, an active `SellerSubscription` bought by the same
  user. Server-side pricing (in `apps/marketplace/subscriptions.py`): the
  monthly plan costs 5 000 FCFA, the semi-annual 10 000 and the annual
  12 000; a user's very first month is offered at 2 500. States
  `pending → active → (renewed|expired)`, plus `cancelled`/`failed`; access
  is always evaluated against the server clock (`expires_at`), never the
  status column alone. Publisher endpoints answer `403`
  `seller_subscription_required` without an active subscription, the public
  catalog only lists products whose owner is currently subscribed
  (hidden-but-kept when the subscription lapses, restored on renewal), and
  checkout/payment reuse the M5b sandbox `Payment`/webhook machinery with a
  `subscription_reference` payload target (same HMAC, same idempotency).
  Housekeeping: `expire_marketplace_subscriptions` flips lapsed rows and
  cancels never-paid checkouts.

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
- **M4b (done):** training reports on top of the same engine — trainee
  progress (per placement: examiners, assessment breakdown), competency
  assessment report (assessor/trainee views), examiner review history,
  placement completion (with an honest `n/a` completion when no assessment
  exists rather than a misleading 0%), institution-level aggregated summary;
  optional `target_user` restricted to supervisors/managers, structured
  columns only (assessment feedback and decision reasons never leave the
  platform), report jobs bounded to the job's institution — 19 new tests
  (245 total). Milestone 4 complete.
- **M5a (done):** `apps.marketplace` — supplier registration and platform
  verification/suspension, product categories and an approval workflow
  (supplier lists a product as `pending`, platform admin approves or
  rejects), integer XOF pricing, inventory with reserved quantities and a
  `reserved ≤ available` CHECK, restock movements, buyer-only cart and
  checkout (row locks prevent overselling, one order per supplier,
  line-item snapshots, `ORD-YYYY-XXXXXX` references), order history with
  buyer/supplier scoping and cancellation that releases reservations and
  logs the release; audit events `marketplace.*` — 20 new tests
  (265 total).
- **M5b (done):** sandbox payment settlement and the rest of the marketplace
  lifecycle — `Payment`/`PaymentEvent` with HMAC-verified webhooks
  (idempotent, amount+currency matched, mock refused when
  `PAYMENTS_ACCEPT_MOCK=False`, payloads redacted), 24 h payment-window
  expiry command that releases stock, stock consumption on settlement
  (`sold`) and restock on refund, `Shipment` (ship/deliver), full-order
  refunds (buyer requests, supplier decides, state + inventory settled once),
  disputes with private-storage evidence + authenticated download and
  platform-admin resolution (buyer-favored auto-refunds), marketplace
  reports (`supplier_sales`, `buyer_orders`, `marketplace_summary`) on the
  existing CSV/PDF engine with a nullable `ReportJob.institution` — 47 new
  tests (312 total). Milestone 5 complete.
- **M6 (in progress):** React 19 + Vite + TypeScript web client (`web/`) with
  TanStack Query for server state and React Router for navigation. Implemented
  workspaces: authentication and account security, role-aware dashboard,
  surgical logbook (list/create/detail with inline draft editing, attachments,
  dictation, participants, review history), training (placements list/detail/
  create, competency catalog and rubric history, assessments list/create/
  detail), reports, marketplace (catalog, product detail, cart/checkout, orders
  with sandbox payment, shipping, refund and dispute actions), notifications,
  institution administration (profile, departments, members/roles,
  invitations, audit), supplier workspace (profile/verification, catalog,
  inventory restock, orders) and platform administration (supplier
  verification, product moderation, categories, disputes, audit).
  Navigation items are role-filtered and each workspace repeats the check so a
  direct URL cannot bypass the UI gate; the API remains the authority.
  **Outstanding:** the Flutter mobile client.
- **M7:** per README milestones.

- **M9a (done):** `apps.legal` — Policies & Legal Center backend. `Policy`
  (stable slug, category, linked `related_policies`) plus `PolicyVersion`
  texts carrying their own lifecycle (`draft` → `pending_review` →
  `approved` → `published` → `superseded`/`archived`), an explicit EN↔FR
  `translation_of` link, effective/review dates and version numbers unique
  per language with one published version per (policy, language) enforced
  at the DB level. Public reads (`/legal/policies/`, `/legal/policies/<slug>/
  ?lang=…`, version history) always resolve the *published* text — a draft
  can never leak into a published slot. `PolicyConsent` records the exact
  accepted version (+ context and optional withdrawal, never deleted) and
  registration now requires the current published Terms version (validated
  server-side, consent recorded with the account, atomic). Privacy requests
  (access/export/deletion/correction) with user-opened + admin-review
  workflow. Admin lifecycle endpoints (create draft, submit-review, approve,
  publish with automatic supersede, archive) restricted to platform admins;
  every transition audited (`legal.*`). Seed command `seed_legal` publishes
  the six bilingual policy texts v1.0 with operator placeholders; 21 new
  tests (370 total). **Web & mobile UI follow in M9b/M9c.**
