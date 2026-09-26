"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

type Project = {
  id: string;
  title: string;
};

type EvidenceDocument = {
  id: string;
  filename: string;
  processing_status: string;
};

type FactCandidate = {
  id: string;
  machine_id: string | null;
  source_kind: string;
  document_id: string | null;
  document_page_id: string | null;
  verification_result_id: string | null;
  fact_key: string;
  raw_value: string;
  normalized_value: unknown;
  unit: string | null;
  confidence: number | null;
  source_excerpt: string;
  extraction_method: string;
  extraction_version: string;
  effective_date: string | null;
  review_state: string;
  reviewed_value: unknown | null;
};

type ExtractionResult = {
  candidates_created: number;
  candidates_existing: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ORGANIZATION_ID =
  process.env.NEXT_PUBLIC_DEV_ORGANIZATION_ID ??
  "11111111-1111-1111-1111-111111111111";
const REVIEWER_ID =
  process.env.NEXT_PUBLIC_DEV_REVIEWER_ID ?? "development-engineer";

function displayValue(value: unknown, unit: string | null) {
  const rendered =
    typeof value === "string" || typeof value === "number"
      ? String(value)
      : JSON.stringify(value);
  return unit ? `${rendered} ${unit}` : rendered;
}

export default function FactReviewPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<EvidenceDocument[]>([]);
  const [candidates, setCandidates] = useState<FactCandidate[]>([]);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const baseHeaders = useMemo(
    () => ({ "X-Organization-Id": ORGANIZATION_ID }),
    [],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectResponse, documentsResponse, candidatesResponse] =
        await Promise.all([
          fetch(`${API_BASE}/api/v1/projects/${projectId}`, {
            headers: baseHeaders,
          }),
          fetch(`${API_BASE}/api/v1/projects/${projectId}/documents`, {
            headers: baseHeaders,
          }),
          fetch(`${API_BASE}/api/v1/projects/${projectId}/fact-candidates`, {
            headers: baseHeaders,
          }),
        ]);

      if (!projectResponse.ok) {
        throw new Error(`Project request failed: ${projectResponse.status}`);
      }
      if (!documentsResponse.ok) {
        throw new Error(`Evidence request failed: ${documentsResponse.status}`);
      }
      if (!candidatesResponse.ok) {
        throw new Error(
          `Fact candidate request failed: ${candidatesResponse.status}`,
        );
      }

      setProject((await projectResponse.json()) as Project);
      setDocuments((await documentsResponse.json()) as EvidenceDocument[]);
      setCandidates((await candidatesResponse.json()) as FactCandidate[]);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load fact review workspace",
      );
    } finally {
      setLoading(false);
    }
  }, [baseHeaders, projectId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function extractParsedDocuments() {
    const parsed = documents.filter(
      (document) => document.processing_status === "PARSED",
    );
    if (parsed.length === 0) {
      setError("Parse at least one evidence document before extracting facts.");
      return;
    }

    setExtracting(true);
    setError(null);
    setNotice(null);

    try {
      let created = 0;
      let existing = 0;

      for (const document of parsed) {
        const response = await fetch(
          `${API_BASE}/api/v1/documents/${document.id}/extract-facts`,
          {
            method: "POST",
            headers: baseHeaders,
          },
        );
        if (!response.ok) {
          throw new Error(
            `Extraction failed for ${document.filename}: ${response.status}`,
          );
        }

        const result = (await response.json()) as ExtractionResult;
        created += result.candidates_created;
        existing += result.candidates_existing;
      }

      setNotice(
        `${created} new candidate(s) created; ${existing} already existed. All new candidates remain PROPOSED.`,
      );
      await loadData();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not extract fact candidates",
      );
    } finally {
      setExtracting(false);
    }
  }

  async function reviewCandidate(
    candidate: FactCandidate,
    action: "CONFIRMED" | "CORRECTED" | "REJECTED",
  ) {
    setReviewingId(candidate.id);
    setError(null);
    setNotice(null);

    try {
      let correctedValue: unknown | undefined;
      if (action === "CORRECTED") {
        const correction = corrections[candidate.id]?.trim();
        if (!correction) {
          throw new Error("Enter a corrected value before selecting Correct.");
        }

        if (typeof candidate.normalized_value === "number") {
          const parsed = Number(correction.replace(",", "."));
          if (!Number.isFinite(parsed)) {
            throw new Error("Corrected numeric value must be a valid number.");
          }
          correctedValue = parsed;
        } else {
          correctedValue = correction;
        }
      }

      const response = await fetch(
        `${API_BASE}/api/v1/fact-candidates/${candidate.id}/review`,
        {
          method: "POST",
          headers: {
            ...baseHeaders,
            "Content-Type": "application/json",
            "X-Reviewer-Id": REVIEWER_ID,
          },
          body: JSON.stringify({
            action,
            ...(action === "CORRECTED"
              ? { corrected_value: correctedValue }
              : {}),
          }),
        },
      );

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(payload?.detail || `Review failed: ${response.status}`);
      }

      setNotice(`${candidate.fact_key} marked ${action}.`);
      await loadData();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not review fact candidate",
      );
    } finally {
      setReviewingId(null);
    }
  }

  if (loading && !project) {
    return (
      <main>
        <section>
          <p className="eyebrow">Fact review</p>
          <h1>Loading candidates…</h1>
        </section>
      </main>
    );
  }

  const proposedCount = candidates.filter(
    (candidate) => candidate.review_state === "PROPOSED",
  ).length;

  return (
    <main>
      <section>
        <p className="eyebrow">Slice 4 · Human review</p>
        <h1>{project?.title ?? "Project"} facts</h1>
        <p className="lead">
          Extraction creates traceable proposals only. An engineer must confirm,
          correct, or reject every value before it can be treated as reviewed.
        </p>
        <div className="actions">
          <Link href={`/projects/${projectId}`}>← Evidence workspace</Link>
          <Link href={`/projects/${projectId}/state`}>State reconstruction →</Link>
          <span className="status">{candidates.length} candidate(s)</span>
          <span className="status">{proposedCount} proposed</span>
        </div>
      </section>

      <section>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Deterministic baseline</p>
            <h2>Extract candidates</h2>
          </div>
          <button
            className="button"
            disabled={extracting}
            onClick={() => void extractParsedDocuments()}
            type="button"
          >
            {extracting ? "Extracting…" : "Extract from parsed evidence"}
          </button>
        </div>
        <p className="section-copy">
          This baseline uses deterministic rules against the synthetic golden
          pack. It is intentionally not an LLM and does not choose a current
          machine state.
        </p>
        {notice ? <p className="notice">{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Provenance-first proposals</p>
            <h2>Fact candidates</h2>
          </div>
          <button
            className="secondary-button"
            onClick={() => void loadData()}
            type="button"
          >
            Refresh
          </button>
        </div>

        {candidates.length === 0 ? (
          <div className="empty-state">
            <strong>No fact candidates yet.</strong>
            <p>Parse evidence first, then run deterministic extraction.</p>
          </div>
        ) : (
          <div className="fact-list">
            {candidates.map((candidate) => {
              const isReviewing = reviewingId === candidate.id;
              const effectiveValue =
                candidate.review_state === "CORRECTED"
                  ? candidate.reviewed_value
                  : candidate.normalized_value;

              return (
                <article className="fact-card" key={candidate.id}>
                  <div className="fact-card-header">
                    <div>
                      <p className="eyebrow">{candidate.fact_key}</p>
                      <h3>
                        {displayValue(effectiveValue, candidate.unit)}
                      </h3>
                    </div>
                    <span className="status">{candidate.review_state}</span>
                  </div>

                  {candidate.review_state === "CORRECTED" ? (
                    <p className="fact-original">
                      Original proposal:{" "}
                      {displayValue(candidate.normalized_value, candidate.unit)}
                    </p>
                  ) : null}

                  <blockquote className="source-excerpt">
                    {candidate.source_excerpt}
                  </blockquote>

                  <div className="fact-meta-grid">
                    <span>
                      Confidence:{" "}
                      {candidate.confidence === null
                        ? "n/a"
                        : `${Math.round(candidate.confidence * 100)}%`}
                    </span>
                    <span>
                      Date: {candidate.effective_date || "not established"}
                    </span>
                    <span>
                      Source:{" "}
                      {candidate.source_kind === "FIELD_VERIFICATION"
                        ? `field verification ${candidate.verification_result_id?.slice(0, 8) ?? "unknown"}…`
                        : `${candidate.document_id?.slice(0, 8) ?? "document"}… / ${candidate.document_page_id?.slice(0, 8) ?? "page"}…`}
                    </span>
                    <span>
                      Extractor: {candidate.extraction_method}{" "}
                      {candidate.extraction_version}
                    </span>
                    <span>
                      Scope: {candidate.machine_id ? "machine-linked" : "project-level"}
                    </span>
                  </div>

                  <div className="fact-review-controls">
                    <button
                      className="secondary-button"
                      disabled={isReviewing}
                      onClick={() => void reviewCandidate(candidate, "CONFIRMED")}
                      type="button"
                    >
                      Confirm
                    </button>

                    <label className="correction-field">
                      <span>Correction</span>
                      <input
                        value={corrections[candidate.id] ?? ""}
                        onChange={(event) =>
                          setCorrections((current) => ({
                            ...current,
                            [candidate.id]: event.target.value,
                          }))
                        }
                        placeholder={String(candidate.normalized_value)}
                      />
                    </label>

                    <button
                      className="secondary-button"
                      disabled={isReviewing}
                      onClick={() => void reviewCandidate(candidate, "CORRECTED")}
                      type="button"
                    >
                      Correct
                    </button>
                    <button
                      className="secondary-button"
                      disabled={isReviewing}
                      onClick={() => void reviewCandidate(candidate, "REJECTED")}
                      type="button"
                    >
                      Reject
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
