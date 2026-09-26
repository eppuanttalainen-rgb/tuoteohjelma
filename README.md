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
- PDF parser: pypdf 6.19.0
- AI: provider adapter boundary (implemented later)
- Evidence storage: local object-storage adapter for development; S3-compatible production adapter planned behind the same boundary

## Repository structure

```text
apps/
  api/
    app/      FastAPI application
    scripts/  deterministic synthetic test-data tooling
    tests/
  web/        Next.js application
docs/
  architecture/
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

### Slice 2 — evidence ingestion

- tenant-aware Document model
- PDF upload endpoint
- PDF MIME and magic-signature validation
- configurable upload size limit
- SHA-256 hashing
- duplicate detection
- optional machine association
- project evidence inventory
- project evidence workspace UI

### Slice 3 — parsing and provenance

- pypdf 6.19.0 pinned as the deterministic parser version
- tenant-aware DocumentPage model
- page number + extracted text
- page-level SHA-256
- parser name/version provenance
- parsing state transitions
- explicit PARSE_FAILED state
- reparse replaces prior parsed pages
- parsed-page read API
- provenance UI
- deterministic synthetic PDF test factory
- CV-204 golden regression pack generator

### Slice 4 — fact candidates and human review

- tenant-aware FactCandidate model
- append-only FactReview audit records
- deterministic golden-v1 extraction baseline
- exact DocumentPage provenance for every candidate
- raw + normalized values and engineering units
- extraction confidence and method/version metadata
- effective date when explicitly available in evidence
- PROPOSED by default; never auto-confirmed
- confirm / correct / reject review workflow
- corrections preserve the original extracted value
- source documents become provenance-locked after fact extraction
- fact-review workspace in the web UI
- CV-204 regression coverage for 11 kW original, 15 kW replacement, unrelated 7.5 kW evidence, and ambiguous guard-switch data

### Slice 5 — reviewed-fact reconciliation (current)

- only CONFIRMED/CORRECTED fact candidates participate
- deterministic reviewed-fact reconciliation v1
- DERIVED state when reviewed evidence agrees or chronology is explicit
- SUPERSEDED evidence retained as history
- DISPUTED state when reviewed values conflict without reliable ordering
- UNKNOWN state for reviewed but incomplete/ambiguous values
- verification tasks for unresolved conflicts
- missing referenced-document task for evidence such as RA-2022-17
- project-level facts cannot automatically override machine-linked state
- assertion -> candidate -> page -> document traceability
- idempotent reconciliation
- state/history/verification workspace in the web UI

External LLM extraction, OCR, compliance interpretation, and autonomous legal/safety judgment are intentionally **not active yet**.

## Golden synthetic pack

Generate the complete CV-204 regression dataset without committing binary evidence to Git:

```bash
cd apps/api
python -m scripts.generate_golden_pack --output tmp/golden_cv204
```

The generated pack contains eight synthetic PDFs plus `manifest.json`, including:

- 2009 original 11 kW motor evidence
- 2021 15 kW motor replacement
- ABB ACS580 drive replacement
- Siemens S7-300 PLC inventory
- 2022 light-curtain modification
- a referenced but intentionally missing risk assessment
- an unrelated 7.5 kW motor datasheet
- an ambiguous guard-switch field note
- a byte-for-byte duplicate OEM manual

The pack is generated deterministically and is regression-tested with the same parser used by the application.

## Evidence storage

Development evidence is stored outside Git under a Docker-managed evidence volume. The application stores only a storage key and metadata in PostgreSQL.

Do not commit evidence files to the repository.

The current storage adapter is intentionally replaceable so an encrypted S3-compatible or customer-specific object store can be introduced before production pilots.

## Parser, fact, and reconstructed-state provenance

PDF text is stored page by page. Each parsed page records:

- source document
- page number
- normalized extracted text
- text SHA-256
- parser name
- parser version

The parser version is part of provenance because PDF text extraction behavior can change between parser releases.

Image-only pages may produce no text. OCR is deliberately deferred to a later fallback path.

After fact extraction, the source document is locked against in-place reparsing. This prevents reviewed candidates from silently pointing at changed source text. A future parser-upgrade workflow should create a versioned source lineage rather than mutating reviewed provenance.

Every fact candidate stores its source document/page, exact source excerpt, extraction method/version, confidence, normalized value and review state. Human corrections are stored separately from the original extraction, and review actions are audit-recorded with a reviewer reference.

Reconciliation consumes reviewed facts only. A derived state keeps explicit evidence relationships such as SUPPORTS, SUPERSEDED, or CONFLICTS. Ambiguity is surfaced as UNKNOWN/DISPUTED plus a verification task instead of being hidden behind a guessed current value.

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
- parser/golden-pack regression tests
- fact extraction/review regression tests
- reconciliation chronology/conflict regression tests
- verification-task regression tests
- provenance-lock regression tests
- tenant-isolation tests
- Ruff lint for app, tests, migrations and scripts
- Next.js production build
