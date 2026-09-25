# Machine Compliance Intelligence

AI-first brownfield machine reconstruction for retrofit, automation, and integration projects.

## Current scope

The MVP focuses on three things:

1. reconstruct the current machine state from fragmented legacy evidence,
2. reconcile contradictions and missing information,
3. turn uncertainty into field-verification tasks.

It intentionally does **not** attempt to certify machinery, replace a qualified engineer, or provide an automatic legal compliance verdict.

## Working product promise

> Upload what you have. We reconstruct what the machine is, show what we can prove, and tell you what still needs to be verified before you modify it.

## Architecture

- Web: Next.js 16 + TypeScript
- API: FastAPI + Python
- Database: PostgreSQL 18
- Local orchestration: Docker Compose
- AI: provider adapter boundary (implemented later)
- Evidence storage: local object-storage adapter for development; S3-compatible production adapter planned behind the same boundary

## Repository structure

```text
apps/
  api/        FastAPI service
  web/        Next.js application
docs/
  architecture/
infra/
docker-compose.yml
```

## Local development

1. Copy environment values:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up --build
```

3. Open:

- Web: http://localhost:3000
- Projects: http://localhost:3000/projects
- API: http://localhost:8000
- API health: http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/docs

The API container automatically runs `alembic upgrade head` before starting.

## Implemented slices

### Slice 0 — foundation

- Next.js web app
- FastAPI API
- PostgreSQL
- Docker Compose
- GitHub Actions CI
- health endpoint
- architecture decision separating machine truth from compliance logic

### Slice 1 — projects and machines

- tenant-aware Project and Machine models
- create/list/read APIs
- PostgreSQL migrations
- tenant-isolation tests
- Projects UI

### Slice 2 — evidence ingestion (current)

- tenant-aware Document model
- PDF upload endpoint
- PDF MIME and magic-signature validation
- configurable upload size limit
- SHA-256 hashing
- duplicate detection
- optional machine association
- project evidence inventory
- project evidence workspace UI

Automated extraction, OCR, reconciliation, and compliance interpretation are intentionally **not active yet**.

## Evidence storage

Development evidence is stored outside Git under a Docker-managed evidence volume. The application stores only a storage key and metadata in PostgreSQL.

Do not commit evidence files to the repository.

The current storage adapter is intentionally replaceable so an encrypted S3-compatible or customer-specific object store can be introduced before production pilots.

## Security boundary

This repository is currently public.

Until Security Gate #4 is closed:

- use synthetic or explicitly non-sensitive PDFs only,
- do not commit customer drawings, manuals, machine files, credentials, API keys, or pilot identities,
- do not use the prototype as a production customer-document repository.

## Core engineering principles

- Evidence before conclusions.
- Every important extracted fact must retain provenance.
- AI proposes; engineers confirm.
- New evidence must not silently overwrite confirmed historical facts.
- Machine truth is separate from jurisdiction-specific regulatory logic.
- International-first architecture: localization-ready UI, canonical SI units, modular jurisdictions.
- Confidential industrial evidence must be treated as sensitive data.

## CI baseline

Pull requests are validated with:

- PostgreSQL 18 service startup
- Alembic migrations
- API tests
- tenant-isolation tests
- Ruff lint
- Next.js production build
