# ADR-001: Keep machine truth separate from compliance logic

**Status:** Accepted  
**Date:** 2026-09-25

## Context

The product starts with brownfield machine reconstruction. The same physical machine may later be evaluated under different jurisdictions and at different points in its lifecycle.

If regulatory conclusions are embedded directly into the core machine record, the product becomes difficult to internationalize and historical evidence becomes entangled with changing rules.

## Decision

The core data model stores machine facts, evidence, chronology, conflicts, verification state, and snapshots independently of jurisdiction-specific compliance logic.

Future regulatory packs consume the machine record. They do not own or redefine the underlying facts.

## Consequences

- A machine record remains useful even without a compliance pack.
- EU, UK, US, and later jurisdictions can share the same factual machine state.
- Changes to legislation do not require rewriting historical machine truth.
- Automated outputs should distinguish evidence state from compliance interpretation.
