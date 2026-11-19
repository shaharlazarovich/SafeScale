# SafeScale Test Suite

## Prerequisites

- **Docker** (for PostgreSQL and LocalStack test containers)
- **Python 3.12+** with the backend dev dependencies installed
- **pytest** and **pytest-asyncio**

## Setup

### 1. Install backend dependencies

```bash
cd backend
pip install -e ".[dev]"
```

### 2. Start test infrastructure

```bash
docker compose -f tests/docker-compose.test.yml up -d
```

This starts:
- **PostgreSQL** on port `5433` (isolated from dev on 5432)
- **LocalStack** on port `4567` (isolated from dev on 4566)

Wait for healthy status:

```bash
docker compose -f tests/docker-compose.test.yml ps
```

### 3. Verify connectivity

```bash
# Postgres
pg_isready -h localhost -p 5433 -U safescale_test

# LocalStack
curl http://localhost:4567/_localstack/health
```

## Running Tests

### Full suite

```bash
pytest tests/ -v
```

### By module

```bash
pytest tests/module1_auditor/ -v
pytest tests/module2_planner/ -v
pytest tests/module3_advisor/ -v
pytest tests/module4_safety_net/ -v
pytest tests/module5_gameday/ -v
pytest tests/module6_drift_detector/ -v
pytest tests/cross_module/ -v
```

### By test layer

```bash
pytest tests/ -m unit              # Unit tests only (~5 min)
pytest tests/ -m integration       # Integration tests (~15 min)
pytest tests/ -m api               # API endpoint tests (~10 min)
pytest tests/ -m e2e               # End-to-end tests (~30 min)
```

### Single test file

```bash
pytest tests/module1_auditor/unit/test_ha_classifier.py -v
```

### Single test

```bash
pytest tests/module1_auditor/unit/test_ha_classifier.py::TestRDSClassification::test_rds_multi_az_is_eligible -v
```

## Coverage

### Generate HTML coverage report

```bash
pytest tests/ --cov=backend/app --cov-report=html:reports/coverage --cov-report=term-missing
```

Open `reports/coverage/index.html` in a browser.

### Generate XML coverage (for CI dashboards)

```bash
pytest tests/ --cov=backend/app --cov-report=xml:reports/coverage.xml
```

## CI Mode

Produces JUnit XML and coverage in one command:

```bash
pytest tests/ \
  --junitxml=reports/junit.xml \
  --cov=backend/app \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=term-missing \
  --tb=short
```

## Tear Down

```bash
docker compose -f tests/docker-compose.test.yml down
```

Add `-v` to also remove volumes:

```bash
docker compose -f tests/docker-compose.test.yml down -v
```
