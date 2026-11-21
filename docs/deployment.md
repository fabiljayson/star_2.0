# Deploying STAR to production

This guide takes the working prototype from `make it run on my laptop` to
`running on a server behind HTTPS`. It assumes a single Linux host (the
architecture is intentionally boring: one Postgres, one Django app). Scale
later by moving Postgres to a managed service and app servers behind a load
balancer — nothing in this guide presumes a specific cloud.

> **Read this first:** STAR ships with a **sandbox (mock) payment provider**
> and a **mock transcription provider**. Both are integrations to be swapped
> for real services before any real money or real voice dictation flows
> through the system — see [Mock integrations](#mock-integrations-you-must-swap).
> STAR also stores clinical data: a legal/contractual review (GDPR or local
> equivalent, data-processing agreements, retention policy) is mandatory
> before real patient data enters the system.

## Contents

- [1. Host prerequisites](#1-host-prerequisites)
- [2. Environment variables](#2-environment-variables)
- [3. Database](#3-database)
- [4. Application server](#4-application-server)
- [5. HTTPS reverse proxy](#5-https-reverse-proxy)
- [6. Scheduled commands (cron)](#6-scheduled-commands-cron)
- [7. Go-live checklist](#7-go-live-checklist)
- [8. Monitoring and recovery](#8-monitoring-and-recovery)
- [Mock integrations you must swap](#mock-integrations-you-must-swap)

---

## 1. Host prerequisites

- Linux host with Python 3.14+, `uv`, Docker + Compose (for Postgres), Nginx
  or Caddy, and `cron`.
- A domain name pointing at the host, with ports 80/443 open.
- A non-root deployment user (example below: `star`), paths:

```text
/srv/star/         # git checkout of the star repo
/srv/star/.env     # secrets (mode 600, owned by star)
/srv/star/backend/
/srv/media/        # PRIVATE_MEDIA_ROOT — served by NO one except Django
```

Clone and install:

```bash
sudo -iu star
git clone git@github.com:fabiljayson/star_2.0.git /srv/star
cd /srv/star/backend
uv venv && uv pip install -e .
```

## 2. Environment variables

Copy `.env.example` to `.env` (repo root) and change **every** value below
before the first boot:

| Variable | Production value | Why |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` | Enables the production hardening block (SSL, HSTS, security headers, mock-payments kill-switch). Verified by tests. |
| `DJANGO_SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(64))"` | Anything starting with `dev-only` or empty **refuses to boot** in production. |
| `DJANGO_ALLOWED_HOSTS` | your real domain, e.g. `star.example.org` | Production boots fail without it. |
| `DJANGO_DEBUG` | `false` (or unset) | `production` forces `DEBUG=False` regardless. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://star.example.org` | CSRF checks for browser form posts. |
| `CORS_ALLOWED_ORIGINS` | `https://star.example.org` (or remove) | Never `*` in production. |
| `POSTGRES_*` | strong password, real db name | Defaults are dev-only. |
| `PAYMENT_WEBHOOK_SECRET` | `secrets.token_urlsafe(48)` | HMAC key for payment webhooks. |
| `REQUIRE_EMAIL_VERIFICATION` | `true` | Sends verification links on registration. |
| `REQUIRE_MFA_FOR_PLATFORM_ADMINS` | `true` (recommended) | Platform admins must enrol TOTP before privileged actions. |
| `FRONTEND_URL` | `https://star.example.org` | Used in verification / password-reset links. |
| `PRIVATE_MEDIA_ROOT` | `/srv/media` | Clinical attachments outside any web-served path. |
| `SECURE_HSTS_SECONDS` | `31536000` | Start with `86400` only if pre-existing domains share the host. |

Full reference with comments lives in `.env.example`.

### Vercel demo deployment (demo only)

`vercel.json` deploys the showcase (API service + Vite site) and seeds the
legal drafts. It contains **no credentials**. To seed the shared demo
administrator and showcase dataset, set `DEMO_ADMIN_PASSWORD` in the Vercel
project environment; when it is unset the build skips demo seeding and no
administrator is created (use `createsuperuser` instead).

Two constraints make this a demo topology, not production:

- The backend filesystem is ephemeral, so `PRIVATE_MEDIA_ROOT` is not durable
  and clinical attachments are lost on redeploy. Use the single-host layout
  above when files must survive.
- `seed_legal` creates agreements in **draft**; they must still be reviewed and
  published by an administrator, and legal review remains mandatory.

---

## 3. Database

Keep the shipped `docker-compose.yml` for Postgres, editing `.env` so the
container reads the production credentials:

```bash
cd /srv/star
docker compose up -d     # waits for the pg_isready healthcheck
```

Create the schema and an admin account:

```bash
cd /srv/star/backend
DJANGO_SETTINGS_MODULE=config.settings.production \
  uv run python manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings.production \
  uv run python manage.py createsuperuser
```

Tighten permissions and test the connection settings live:

```bash
chmod 600 /srv/star/.env
DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py check
DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py check --deploy
```

`check --deploy` prints Django's own production readiness warnings — fix all
of them before exposing the service.

**Backups** (non-negotiable for a clinical logbook). Nightly dump + 30-day
retention via cron:

```cron
30 3 * * * docker exec star-postgres pg_dump -U star star | gzip > /srv/backups/star-$(date +\%F).sql.gz && find /srv/backups -name 'star-*.sql.gz' -mtime +30 -delete
```

Store at least one copy off-host. Test a restore (`zcat dump | docker exec -i
star-postgres psql -U star star`) before go-live, not after an incident.

## 4. Application server

STAR ships `gunicorn` as a dependency. WSGI only — no ASGI/worker features
are used, so no extra process manager is needed.

```bash
cd /srv/star/backend
DJANGO_SETTINGS_MODULE=config.settings.production \
DJANGO_SECRET_KEY="$(grep -oP '(?<=^DJANGO_SECRET_KEY=).*' /srv/star/.env)" \
  uv run gunicorn config.wsgi:application \
  --bind 127.0.0.1:8002 --workers 4 --timeout 60
```

Run it under systemd so restarts survive reboots
(`/etc/systemd/system/star.service`):

```ini
[Unit]
Description=STAR API (gunicorn)
After=network.target docker.service
Requires=docker.service

[Service]
User=star
WorkingDirectory=/srv/star/backend
EnvironmentFile=/srv/star/.env
ExecStart=/usr/bin/env uv run gunicorn config.wsgi:application --bind 127.0.0.1:8002 --workers 4 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now star
curl -fsS http://127.0.0.1:8002/api/v1/health/
```

Static assets (Django admin + API docs) are collected once per release:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py collectstatic --noinput
```

Serve `/static/` and `/admin/static/` paths from the proxy pointing at
`backend/staticfiles/`, or let Django serve them (`--insecure` is **not**
acceptable in production — prefer the proxy route).

## 5. HTTPS reverse proxy

`config/settings/production.py` already sets `SECURE_PROXY_SSL_HEADER =
("HTTP_X_FORWARDED_PROTO", "https")`, so the proxy must send
`X-Forwarded-Proto`. Minimal Nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name star.example.org;

    ssl_certificate     /etc/letsencrypt/live/star.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/star.example.org/privkey.pem;

    client_max_body_size 15m;   # attachments + audio stay under 10 MB each

    location /static/ {
        alias /srv/star/backend/staticfiles/;
        expires 1y;
    }

    location / {
        proxy_pass         http://127.0.0.1:8002;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   X-Real-IP         $remote_addr;
    }
}
```

Caddy alternative: `star.example.org { reverse_proxy 127.0.0.1:8002 }`
(it sends `X-Forwarded-Proto` automatically).

The web frontend (`web/`) is a static Vite build; `npm run build` and host
`web/dist/` on the same domain (or its own) — it only ever talks to `/api/v1/`.

## 6. Scheduled commands (cron)

One command is mandatory; two housekeeping tasks are optional:

```cron
# Cancel unpaid orders past their TTL (PAYMENT_PENDING_TTL_HOURS) and restock.
# Without it, abandoned checkouts reserve inventory forever.
0 * * * * cd /srv/star/backend && DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py expire_marketplace_orders >> /srv/star/cron.log 2>&1
15 * * * * cd /srv/star/backend && DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py expire_marketplace_subscriptions >> /srv/star/cron.log 2>&1
```

## 7. Go-live checklist

- [ ] `.env` contains production values; `chmod 600`; nothing printed secrets
- [ ] `manage.py check --deploy` reports no errors
- [ ] `GET https://…/api/v1/health/` returns `200` with `database: ok`
- [ ] HTTPS enforced (HTTP → redirect works; HSTS header present)
- [ ] Login + MFA enrol + password reset round-trips over the real domain
- [ ] Upload a PDF attachment, download it again, confirm `Cache-Control: private, no-store`
- [ ] Sandbox payment webhook returns **400** (“Mock payments are disabled…”)
      because `PAYMENTS_ACCEPT_MOCK=False` in production
- [ ] `expire_marketplace_orders` cron entry installed (fake a stale order first)
- [ ] `expire_marketplace_subscriptions` cron entry installed
- [ ] Policy Center: `seed_legal` drafts reviewed by legal counsel, operator
      placeholders (`[[Operator name — to be supplied]]`, contact e-mail,
      liability limits) replaced before any publication
- [ ] Each EN/FR draft approved and published at `/admin/legal`; then
      `GET /api/v1/legal/policies/?lang=fr` lists the six published texts and
      registration accepts the published Terms version
- [ ] Publish a test Terms version and confirm an existing account sees the
      reacceptance banner and gets `403 terms_acceptance_required` on
      checkout until it accepts; then archive the test version
- [ ] Only platform editors publish policy versions; drafts are never
      linked to consents and never served to the public Policy Center
- [ ] Backup taken **and restored** on a scratch instance
- [ ] Platform admin account(s) exist and have MFA enrolled
- [ ] Notification preferences show in-app only; no inert email toggle is offered
- [ ] Vercel demo (if used) has `DEMO_ADMIN_PASSWORD` set as a project secret,
      never in `vercel.json`
- [ ] `docs` + README updated with where the service actually runs

## 8. Monitoring and recovery

- **Liveness:** `GET /api/v1/health/` (checks DB); wire it to uptime
  monitoring (UptimeRobot, Healthchecks.io, …) and alert on non-200.
- **Logs:** gunicorn/journald for app + access logs from Nginx. Django's
  logger is lowered to `WARNING` in production; audit events go to the
  database (append-only), not stdout.
- **Recovery drill:** restore the latest backup on a scratch database, run
  `migrate`, boot Gunicorn against it, log in. Do this quarterly.
  After any restore, re-run pending migrations — schema and data must move
  together.
- **Rotating `DJANGO_SECRET_KEY`** invalidates all outstanding JWTs
  (refresh-token signatures) — planned security events can use the cheaper
  `auth_version` bump (logout everywhere) instead unless the key is suspected
  compromised.
- **Rotating `PAYMENT_WEBHOOK_SECRET`** must be coordinated with the payment
  provider (double-key overlap period if the provider supports it).

## Mock integrations you must swap

| Component | Today | Before real use |
|---|---|---|
| Payments | `PAYMENT_PROVIDER=sandbox`: signed mock webhook | Contract a real PSP; implement its provider in `apps/marketplace/payments.py` (same webhook-verification pattern: signature over canonical JSON, idempotence, amount/currency checks). Keep `PAYMENTS_ACCEPT_MOCK=False` in production. |
| Transcription | `TRANSCRIPTION_PROVIDER=mock`: deterministic en/fr text, banner `SIMULATED`, audio deleted after validation | Contract a speech-to-text service; implement the same provider interface (`apps/logbook/transcription.py`). Audio retention rules: nothing is ever persisted today; build the retention policy WITH your DPO. |
| Email | `.env.example` wires an SMTP block already (`EMAIL_*` keys are consolidated in `MAILERS` — see README troubleshooting). It is used for verification and password-reset mail; notification email is **not implemented** — the preference centre exposes in-app delivery only. | Point at a real SMTP relay; verify from-address SPF/DKIM; hosting provider stuffs e-mail, so use a transactional service. Notification email needs its own delivery implementation before the channel is offered. |

**Updating:** pull code → `uv pip install -e .` → `migrate` → `collectstatic`
→ `systemctl restart star` → curl the health endpoint. Keep changes visible
in one window of downtime, not many.
