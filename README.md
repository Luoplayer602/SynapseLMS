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

