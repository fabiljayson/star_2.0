# Windows setup: PostgreSQL connection timeout

Use these steps if `manage.py migrate` fails with a timeout connecting to
`localhost` on port `5433`.

That timeout means Django cannot reach PostgreSQL. Usually the PostgreSQL
container is not running yet. It does not usually indicate a bad password or
a problem with the migrations.

## 1. Start Docker Desktop

Install Docker Desktop if needed, then open it and wait until it says Docker is
running.

## 2. Open PowerShell in the project folder

In File Explorer, open the folder containing `docker-compose.yml`. Click the
address bar, type `powershell`, and press Enter.

Check that PowerShell is in the right folder:

```powershell
Get-ChildItem docker-compose.yml
```

You should see `docker-compose.yml` listed.

## 3. Start the database

Run this from the project folder:

```powershell
docker compose up -d db
docker compose ps
```

The `db` service should show as running. The project exposes PostgreSQL at
`localhost:5433` on your computer and forwards that to port `5432` in the
container.

If Docker reports that it cannot connect to its engine, open Docker Desktop,
wait for it to finish starting, and retry these commands.

## 4. Check that port 5433 is reachable

In the same PowerShell window, run:

```powershell
Test-NetConnection 127.0.0.1 -Port 5433
```

Look for:

```text
TcpTestSucceeded : True
```

If it says `False`, check the database logs:

```powershell
docker compose logs db
```

Make sure the `db` container is running and that port `5433` is not already
being used by another program. If you change `POSTGRES_PORT` in the project's
root `.env` file, also set the matching `POSTGRES_PORT` in `backend\.env`.
Django reads its settings from `backend\.env`; Docker Compose reads the root
`.env`. The default values match, so you do not need to create either file for
a basic local setup.

## 5. Install the backend dependencies

The project requires Python 3.14 or newer. These commands use Python 3.14,
as specified in the project setup:

```powershell
cd backend
uv python install 3.14
uv sync --python 3.14
```

If PowerShell says `uv` is not recognized, install `uv` using its
[Windows installation instructions](https://docs.astral.sh/uv/getting-started/installation/),
then close and reopen PowerShell.

## 6. Run the migrations

From the `backend` folder, run:

```powershell
uv run --python 3.14 python manage.py migrate
```

When migrations complete, the database is ready. To start the API locally:

```powershell
uv run --python 3.14 python manage.py runserver 0.0.0.0:8002
```

## If it still cannot connect

From the project folder, collect the database status and logs:

```powershell
docker compose ps
docker compose logs db
Test-NetConnection 127.0.0.1 -Port 5433
```

If the port test succeeds but Django still times out, check whether a
`DATABASE_URL` environment variable is set. It overrides the individual
PostgreSQL settings. Also check that any custom database settings use the
same host and port as Docker Compose.
