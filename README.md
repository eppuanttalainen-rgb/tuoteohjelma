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
- Files: S3-compatible object storage (implemented later)

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
- API: http://localhost:8000
- API health: http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/docs

## Core engineering principles

- Evidence before conclusions.
- Every important extracted fact must retain provenance.
- AI proposes; engineers confirm.
- New evidence must not silently overwrite confirmed historical facts.
- Machine truth is separate from jurisdiction-specific regulatory logic.
- International-first architecture: localization-ready UI, canonical SI units, modular jurisdictions.
- Confidential industrial evidence must be treated as sensitive data.

## Status

Slice 0 — foundation. No production customer data is used at this stage.
