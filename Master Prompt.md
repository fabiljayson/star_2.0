# STAR — Master Prompt v2 (post-Milestone 9)

## 0. How to read this document

This file replaces the Milestone 9 implementation brief. The Policies & Legal
Center it described is **delivered**; do not rebuild it, do not re-audit it
from zero, and do not re-open its architecture decisions unless a listed gap
requires a change.

The mission now is **trustworthy delivery**: make the existing platform
verifiably green in continuous integration, remove a small number of real
security/honesty defects, and stop adding surface area. Scope discipline is
part of the work.

Audit the repository again before editing (paths, conventions, current
numbers may have moved), but treat the baseline in §2 as the supported truth
as of **21 November 2026**.

---

## 1. Mission

Deliver **Milestone 10 — Trustworthy delivery**:

1. Continuous integration covers every client, not only backend and web.
2. Committed deployment configuration contains no credentials and no
   ephemeral-storage assumptions presented as production-ready.
3. The notification preference centre exposes only channels that actually
   deliver.
4. Abuse-prone legal endpoints have scoped rate limits.
5. Repository documentation states what is true today.

No new product features are authorized in this milestone. If a proposed
change would add a user-facing capability, stop and ask.

---

## 2. Baseline — delivered and not to be rebuilt

**Backend** (Django 6.1, DRF, PostgreSQL 16, Python 3.14):

- Apps: `accounts`, `core`, `legal`, `logbook`, `marketplace`,
  `notifications`, `organizations`, `reports`, `training`.
- Legal Center: six bilingual policies seeded as **drafts**, immutable
  published versions, single write path (`supersede_published`, approval
  required), consent trail with withdrawal, reacceptance flag and server-side
  marketplace gating, privacy requests with admin review, audit events.
- Verified on 21 Nov 2026: `uv run pytest` → **377 passed**; `ruff` clean;
  `makemigrations --check` → no changes.

**Web** (React 19 + Vite + TypeScript, TanStack Query):

- Full workspaces for auth, dashboard, logbook, training, reports,
  marketplace, notifications, institution/supplier/platform admin, and the
  Legal Center (center, detail, history, consents, privacy requests, admin
  review/edit).
- Verified: `tsc -b` clean, `oxlint` 0 warnings, **84 tests in 23 files**,
  production build succeeds.

**Mobile** (Flutter, `fvm` pinned to stable):

- Auth, dashboard, logbook, marketplace/subscription, notifications, legal
  center (center, detail, history, consents, privacy requests, reacceptance
  banner).
- **20 tests in 6 files**, not executed on this machine (no Flutter SDK, no
  `fvm`). Never report them as passing until CI runs them.

**CI** (`.github/workflows/ci.yml`): backend (ruff, migration check, pytest
against PostgreSQL 16) and web (oxlint, vitest, build). No Flutter job.

**Known environment constraint:** local Docker requires a password-protected
sudo; rootless PostgreSQL via
`uv run --no-project --python 3.12 --with pgserver` was used to run the
suite. CI's service container is the authoritative path.

---

## 3. Assessment

### 3.1 Keep — these are working and should not be redesigned

- **One backend source of truth** shared by web and mobile; no client-side
  consent database.
- **Immutable published versions** plus a database uniqueness constraint for
  one published text per policy and language.
- **One publication path** that accepts only `approved` versions; drafts
  cannot leak through public endpoints.
- **Server-recorded consent** with exact version, language, context,
  timestamp, preserved history, and withdrawal as an event rather than a
  delete.
- **Non-blocking reacceptance**: banner plus a 403
  `terms_acceptance_required` gate on marketplace writes, with account access
  preserved.
- **Audit reuse** instead of a parallel logging system; uniform API error
  envelope; request IDs; object-level permissions.
- **Sandbox payments** with HMAC webhooks and idempotency, clearly separated
  from real money.
- **Synthetic demo data** and explicit policy placeholders instead of invented
  legal facts.
- **Convention-following tests** at the API boundary, not shallow render
  tests.

### 3.2 Not necessary — deliberate non-goals

Do **not** add these; each is disproportionate for a student demonstration or
unsupported by the implementation:

- Cookie-consent banner or analytics consent UI. No analytics/tracking is
  implemented; the Cookie & Data Retention policy says so. Revisit only if
  analytics is actually added.
- A separate consent-purpose model for optional processing. No optional
  processing purpose exists in the product.
- A mobile administrative workflow. Policy administration stays web-only.
- Separate reviewer and approver roles. One platform-admin role with an
  approval event is sufficient for the demo.
- Policy content checksums, e-signature, PDF policy export, or a policy CMS
  beyond the existing draft editor.
- Multi-jurisdiction/legal-entity data, registration numbers, addresses, or
  regulator names. Placeholders stay until the operator supplies facts.
- Languages beyond English and French.
- Real payment-provider integration, Sentry/metrics stacks, or a queue/worker
  tier. The sandbox and in-app notifications are intentional.
- A second routing/localization framework for mobile to remove the
  feature-local `legal_strings.dart`. Record it as debt; do not refactor now.
- The 22-point checklist applied uniformly to every future change. Use the
  gates in §5 instead.

### 3.3 Gaps to close — ordered by risk

| # | Gap | Evidence | Risk |
|---|-----|----------|------|
| G1 | Flutter is not built or tested anywhere in CI | `ci.yml` has only backend and web jobs | Mobile regressions ship silently; the 20 mobile tests have never run in CI |
| G2 | `vercel.json` embeds a demo administrator password and seeds it on every deploy | `seed_demo --admin-password 'Demo!Passw0rd2026'` in the build command | Credential in Git; anyone can sign in as platform admin on a deployed instance |
| G3 | Notification email preference is inert | `NotificationPreference.email` is exposed by API and UI; no notification email is ever sent | Users believe they subscribed to email they will never receive |
| G4 | Legal write endpoints have no scoped throttles | Only `login`, `register`, `password`, `mfa` rates are configured | Privacy-request and consent spam; noisy audit trail |
| G5 | Documentation is stale and contradictory | README says "Milestones 1–7", "mobile outstanding", 327 backend / 57 web tests; mobile section omits the legal center | Misleads reviewers and future agents; undermines the honest-reporting requirement |
| G6 | Vercel deployment uses local private media | `PRIVATE_MEDIA_ROOT` on an ephemeral filesystem | Clinical attachment loss on redeploy; only acceptable if explicitly labelled demo-only |
| G7 | Reacceptance gating covers marketplace writes only | `_require_current_terms` used in marketplace views | Intentional, but undocumented; clinical/logbook writes remain available, which must be a stated decision |

G1–G5 are in scope. G6–G7 are documentation/decision items in this milestone;
changing storage or extending gating requires a separate decision.

---

## 4. Implementation plan

Execute phases in order. Each phase is independently reviewable and must leave
the repository green.

### Phase A — Documentation truth pass (G5)

- Update `README.md`: status line, milestone table, test counts from a fresh
  run, mobile section (legal center included; `fvm` commands), and the
  "Mobile app (experimental)" heading if the feature set no longer fits.
- State the reacceptance scope: marketplace writes gated, account/logbook
  access preserved.
- State that email notification delivery is not implemented (or remove the
  claim after Phase E).
- Refresh `docs/architecture.md` and `docs/deployment.md` only where they are
  factually wrong; do not restructure them.
- Do not put unverified numbers in the README. Run the commands first.

**Acceptance:** every number and status statement matches an executed command;
no "outstanding" claim contradicts a delivered milestone.

### Phase B — CI parity for Flutter (G1)

- Add a `mobile` job to `.github/workflows/ci.yml` using
  `subosito/flutter-action@v2` with the stable channel and pub cache enabled.
- Steps: `flutter pub get`, `flutter analyze`, `flutter test`.
- Working directory `mobile`; no secrets; no emulator or build artifacts.
- If analysis fails, fix the reported defects rather than relaxing the gate.
  Do not add `// ignore:` comments to pass analysis.

**Acceptance:** the job runs on push and pull request; `flutter analyze` and
all mobile tests pass in CI; failures are visible, not skipped.

### Phase C — Deployment credential hygiene (G2)

- Remove the literal administrator password from `vercel.json`.
- Preferred: stop seeding demo accounts in the build command. Document the
  one-time `createsuperuser` / `seed_demo --admin-password "$ADMIN_PASSWORD"`
  step for deployments.
- If demo seeding must stay for the showcase deployment, read the password
  from an environment variable and fail the build when it is unset; never
  commit a fallback value.
- Do not rotate or delete existing accounts as part of this change.

**Acceptance:** `git grep` finds no password in tracked deployment config; a
deploy without the environment variable does not create an administrator.

### Phase D — Scoped throttles for legal writes (G4)

- Add `ScopedRateThrottle` (or the project's existing throttle pattern) to
  consent creation/withdrawal and privacy-request creation.
- Suggested rates: consent writes `20/hour`, privacy requests `5/hour` per
  user. Put them in `DEFAULT_THROTTLE_RATES` so they are configurable.
- Return the existing `throttled` error envelope; do not change public read
  endpoints.
- Add API tests: the limit triggers, the response is 429 with `Retry-After`,
  and normal use below the limit still succeeds.

**Acceptance:** new tests fail without the throttle and pass with it; no other
endpoint changes behaviour.

### Phase E — Make notification channels honest (G3)

Choose exactly one, and document the choice:

- **Option 1 (recommended for this milestone):** remove the `email` field from
  the preference serializer/UI and expose in-app only, with a note that email
  delivery is not implemented. Keep the database column for a later
  migration-free re-enable.
- **Option 2:** implement email delivery for every exposed category through
  Django's configured email backend, respecting the preference, with tests
  using the locmem backend and graceful failure when SMTP is unavailable.

Do not leave a toggle that silently does nothing. Do not send policy email
without the preference check.

**Acceptance:** every channel visible in the UI has an exercised delivery path,
or is no longer visible; tests cover the preference behaviour.

### Phase F — Optional confidence work (only if Phases A–E are green)

- **A11y:** add axe-core assertions to the legal pages in vitest (dev
  dependency only), or a documented manual keyboard/screen-reader checklist if
  adding the dependency is rejected.
- **E2E smoke:** one Playwright test covering register with Terms acceptance →
  admin publish → reacceptance banner → 403 gate → acceptance clears it. This
  is the only scenario worth browser automation in the demo; do not build a
  suite.
- Skip both if they would delay A–E.

---

## 5. Guardrails (carried over, still binding)

- Drafts are never presented as approved or binding. Only `approved` versions
  can be published, through the existing single path.
- Published text is immutable; corrections create a new version.
- Consent is recorded server-side against an exact published version; never
  trust a client boolean or timestamp.
- Privacy requests and consent history are readable only by their owner or an
  authorized administrator.
- No invented legal facts, retention periods, addresses, registrations, or
  compliance claims; keep placeholders and identify them.
- No secrets in tracked files, frontend bundles, mobile binaries, logs, or
  fixtures. Synthetic data only.
- Preserve unrelated behaviour and API contracts; no drive-by refactors.
- Report exactly what ran. Never claim a test, build, deployment, or legal
  review that did not happen. If the Flutter SDK is unavailable locally, say
  so and rely on CI.

---

## 6. Verification gates

Run at minimum:

```bash
# backend
cd backend
uv run ruff check .
uv run python manage.py makemigrations --check --dry-run
uv run pytest                     # expect 377+ passing

# web
cd ../web
npx oxlint src
npx tsc -b
npm run test                      # expect 84+ passing
npm run build

# mobile (CI, or locally where fvm is installed)
cd ../mobile
fvm flutter analyze
fvm flutter test                  # expect 20+ passing
```

Plus, for the touched areas: `git grep` for the removed credential, a 429 test
for throttles, and the notification-channel test chosen in Phase E.

Do not weaken assertions, skip tests, or add lint suppressions to reach green.
If PostgreSQL is unavailable, use the CI service container result or the
rootless `pgserver` fallback and report which path was used.

---

## 7. Definition of done

1. README and docs match the code and a fresh test run.
2. CI includes backend, web, and Flutter jobs, all required for merge.
3. No credential exists in tracked deployment configuration.
4. Every visible notification channel either delivers or is gone.
5. Legal write endpoints are throttled and tested.
6. The Vercel/ephemeral-media limitation and the marketplace-only
   reacceptance scope are stated as explicit decisions.
7. Existing functionality is preserved; no legal-center rewrite.
8. A final report lists commands run, results, remaining blockers, and the
   items intentionally not done.

---

## 8. Final delivery report

Provide:

- **Changed:** files and why, grouped by phase.
- **Verified:** exact commands and counts, including CI job results.
- **Not verified:** anything that could not run here, and why.
- **Decisions:** the Phase E option chosen, and any scope refused.
- **Remaining:** known limitations (ephemeral media on Vercel, mobile
  localization debt, legal placeholders, legal review not performed).

## Final instruction

Audit the repository, confirm the baseline in §2, then execute Phases A–E in
order without adding product scope. If a phase cannot be completed because of
missing credentials or tooling, stop at that boundary, report it, and continue
with the next independent phase. Do not rebuild the Policies & Legal Center.
