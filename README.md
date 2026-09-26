# SynapseLMS

Open-source, AI-enabled learning management system for language centers.

## Repository layout

```text
backend/    FastAPI application and tests
frontend/   React + TypeScript application
docs/       Product and architecture documentation
compose.yaml
```

## Local development

### Docker

1. Copy `.env.example` to `.env` and change secrets.
2. Run `docker compose up --build`.
3. Open the frontend at `http://localhost:5173` and API docs at `http://localhost:8000/docs`.

Apply database migrations with `docker compose exec -T api .venv/bin/alembic upgrade head`.
The current Compose configuration copies source into images; it does not hot-reload local edits.
After changing code, rebuild the affected service with `docker compose up -d --build --no-deps api`
or replace `api` with `web`. PostgreSQL can stay running.

Authentication database tests and migration details: [AUTH-01](docs/auth-foundation.md).
Authentication, Root Admin bootstrap and browser tests: [Auth operations](docs/auth-operations.md).
Email verification, recovery, session management and local mailbox: [Account lifecycle](docs/account-lifecycle.md).
Email membership invitations, permissions and acceptance checklist: [Membership invitations](docs/membership-invitations.md).
Student profiles, guardian contacts and manual acceptance: [Student profiles](docs/student-profiles.md).

Student proficiency, center verification, goals and history: [STU-03](docs/student-proficiencies.md).

Teacher profiles, explicit teaching capabilities and credentials: [TCH-01/TCH-02](docs/teacher-profiles.md).
Course catalog, language/level settings, publication and acceptance: [Course catalog](docs/course-catalog.md).

### Without Docker

Backend:

```powershell
Set-Location backend
uv sync --dev
uv run fastapi dev app/main.py
```

Frontend on Windows PowerShell:

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

## Verification

```powershell
Set-Location backend
uv run pytest
uv run ruff check .

Set-Location ../frontend
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

Project planning and decisions are indexed in [docs/README.md](docs/README.md).
