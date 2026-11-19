# SafeScale

On-Demand Availability platform — reduces cloud HA overspend by converting eligible Multi-AZ workloads to single-AZ with automated recovery.

## Tech Stack

- **Backend:** Python 3.12+ / FastAPI / SQLAlchemy / Alembic
- **Frontend:** React 18 / TypeScript / Vite
- **Database:** PostgreSQL 16
- **Cloud SDK:** boto3 (AWS)
- **Testing:** pytest (backend), vitest (frontend), LocalStack (AWS mocking)
- **Containerization:** Docker Compose for local dev

## Project Structure

```
backend/          Python FastAPI backend
  app/
    api/          Route handlers
    core/         Config, database, auth
    models/       SQLAlchemy ORM models
    services/     Business logic (auditor/, planner/, etc.)
    schemas/      Pydantic request/response schemas
    utils/        Shared utilities
  alembic/        Database migrations
frontend/         React TypeScript frontend
  src/
    components/   Reusable UI components
    pages/        Page-level components
    hooks/        Custom React hooks
    services/     API client functions
    types/        TypeScript type definitions
tests/            All test suites (per-module subfolders)
planning/         Product planning documents
docker/           Docker-related configs
```

## Commands

```bash
# Backend
cd backend && pip install -e ".[dev]"       # Install backend with dev deps
uvicorn app.main:app --reload               # Run backend dev server
alembic upgrade head                        # Run DB migrations

# Frontend
cd frontend && npm install                  # Install frontend deps
npm run dev                                 # Run frontend dev server

# Testing
pytest tests/ -v                            # Run all tests
pytest tests/module1_auditor/unit/ -v       # Run auditor unit tests
pytest tests/ -k "unit" -v                  # Run all unit tests
pytest tests/ --cov=backend/app             # Run with coverage

# Docker
docker compose up -d                        # Start all services (Postgres, LocalStack)
docker compose down                         # Stop all services
```

## Conventions

- Backend follows FastAPI patterns: routers in `api/routes/`, business logic in `services/`, Pydantic schemas for validation
- All database access through SQLAlchemy async sessions
- Every API endpoint must have a corresponding test
- Structured JSON logging throughout — never `print()`
- AWS operations use the scanner pattern in `services/auditor/scanners/`
- All environment config via `core/config.py` using pydantic-settings
