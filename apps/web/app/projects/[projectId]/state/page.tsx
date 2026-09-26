"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

type Project = {
  id: string;
  title: string;
};

type FactCandidate = {
  id: string;
  fact_key: string;
  normalized_value: unknown;
  reviewed_value: unknown | null;
  unit: string | null;
  source_excerpt: string;
  effective_date: string | null;
  review_state: string;
  source_kind: string;
  document_id: string | null;
  document_page_id: string | null;
  verification_result_id: string | null;
};

type AssertionEvidence = {
  fact_candidate_id: string;
  relationship: string;
};

type StateAssertion = {
  id: string;
  machine_id: string;
  fact_key: string;
  value: unknown | null;
  unit: string | null;
  status: string;
  derivation_method: string;
  derivation_version: string;
  effective_date: string | null;
};

type StateAssertionDetail = StateAssertion & {
  evidence: AssertionEvidence[];
};

type VerificationTask = {
  id: string;
  machine_id: string;
  fact_key: string;
  reason_code: string;
  reason: string;
  instructions: string;
  status: string;
  resolution_value: unknown | null;
};

type ReconciliationResult = {
  assertions_derived: number;
  assertions_disputed: number;
  assertions_unknown: number;
  assertions_unchanged: number;
  verification_tasks_opened: number;
  verification_tasks_resolved: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ORGANIZATION_ID =
  process.env.NEXT_PUBLIC_DEV_ORGANIZATION_ID ??
  "11111111-1111-1111-1111-111111111111";

function displayValue(value: unknown, unit: string | null) {
  if (value === null || value === undefined) return "Not established";
  const rendered =
    typeof value === "string" || typeof value === "number"
      ? String(value)
      : JSON.stringify(value);
  return unit ? `${rendered} ${unit}` : rendered;
}

function reviewedValue(candidate: FactCandidate) {
  return candidate.review_state === "CORRECTED"
    ? candidate.reviewed_value
    : candidate.normalized_value;
}

export default function StateReconstructionPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const headers = useMemo(
    () => ({ "X-Organization-Id": ORGANIZATION_ID }),
    [],
  );

  const [project, setProject] = useState<Project | null>(null);
  const [assertions, setAssertions] = useState<StateAssertionDetail[]>([]);
  const [candidates, setCandidates] = useState<FactCandidate[]>([]);
  const [tasks, setTasks] = useState<VerificationTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [reconciling, setReconciling] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectResponse, assertionsResponse, tasksResponse, candidatesResponse] =
        await Promise.all([
          fetch(`${API_BASE}/api/v1/projects/${projectId}`, { headers }),
          fetch(`${API_BASE}/api/v1/projects/${projectId}/state-assertions`, {
            headers,
          }),
          fetch(`${API_BASE}/api/v1/projects/${projectId}/verification-tasks`, {
            headers,
          }),
          fetch(`${API_BASE}/api/v1/projects/${projectId}/fact-candidates`, {
            headers,
          }),
        ]);

      if (!projectResponse.ok) {
        throw new Error(`Project request failed: ${projectResponse.status}`);
      }
      if (!assertionsResponse.ok) {
        throw new Error(`State request failed: ${assertionsResponse.status}`);
      }
      if (!tasksResponse.ok) {
        throw new Error(`Verification request failed: ${tasksResponse.status}`);
      }
      if (!candidatesResponse.ok) {
        throw new Error(`Candidate request failed: ${candidatesResponse.status}`);
      }

      const assertionRows = (await assertionsResponse.json()) as StateAssertion[];
      const assertionDetails = await Promise.all(
        assertionRows.map(async (assertion) => {
          const response = await fetch(
            `${API_BASE}/api/v1/state-assertions/${assertion.id}`,
            { headers },
          );
          if (!response.ok) {
            throw new Error(
              `Assertion detail request failed: ${response.status}`,
            );
          }
          return (await response.json()) as StateAssertionDetail;
        }),
      );

      setProject((await projectResponse.json()) as Project);
      setAssertions(assertionDetails);
      setTasks((await tasksResponse.json()) as VerificationTask[]);
      setCandidates((await candidatesResponse.json()) as FactCandidate[]);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load reconstructed state",
      );
    } finally {
      setLoading(false);
    }
  }, [headers, projectId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function reconcile() {
    setReconciling(true);
    setError(null);
    setNotice(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/projects/${projectId}/reconcile`,
        {
          method: "POST",
          headers,
        },
      );
      if (!response.ok) {
        throw new Error(`Reconciliation failed: ${response.status}`);
      }

      const result = (await response.json()) as ReconciliationResult;
      setNotice(
        [
          `${result.assertions_derived} derived`,
          `${result.assertions_disputed} disputed`,
          `${result.assertions_unknown} unknown`,
          `${result.verification_tasks_opened} task(s) opened`,
          `${result.verification_tasks_resolved} resolved`,
        ].join(" · "),
      );
      await loadData();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not reconcile reviewed facts",
      );
    } finally {
      setReconciling(false);
    }
  }

  if (loading && !project) {
    return (
      <main>
        <section>
          <p className="eyebrow">State reconstruction</p>
          <h1>Loading reviewed machine state…</h1>
        </section>
      </main>
    );
  }

  const candidateById = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  const openTasks = tasks.filter((task) => task.status === "OPEN");
  const resolvedTasks = tasks.filter((task) => task.status === "RESOLVED");

  return (
    <main>
      <section>
        <p className="eyebrow">Slice 5 · Reviewed state</p>
        <h1>{project?.title ?? "Project"} state</h1>
        <p className="lead">
          Reconciliation uses only human-reviewed facts. Clear chronology may derive a
          current value; uncertainty stays visible as disputed or unknown and becomes a
          verification task.
        </p>
        <div className="actions">
          <Link href={`/projects/${projectId}/facts`}>← Fact review</Link>
          <Link href={`/projects/${projectId}/snapshots`}>Snapshots & reports →</Link>
          <span className="status">{assertions.length} state assertion(s)</span>
          <span className="status">{openTasks.length} open verification task(s)</span>
        </div>
      </section>

      <section>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Deterministic reconciliation</p>
            <h2>Build reviewed machine state</h2>
          </div>
          <button
            className="button"
            disabled={reconciling}
            onClick={() => void reconcile()}
            type="button"
          >
            {reconciling ? "Reconciling…" : "Reconcile reviewed facts"}
          </button>
        </div>
        <p className="section-copy">
          Project-level evidence never overrides machine-linked evidence automatically.
          Compliance rules are not part of this calculation.
        </p>
        {notice ? <p className="notice">{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Current reconstruction</p>
            <h2>State assertions</h2>
          </div>
          <button
            className="secondary-button"
            onClick={() => void loadData()}
            type="button"
          >
            Refresh
          </button>
        </div>

        {assertions.length === 0 ? (
          <div className="empty-state">
            <strong>No reconstructed state yet.</strong>
            <p>Review fact candidates, then run reconciliation.</p>
          </div>
        ) : (
          <div className="state-list">
            {assertions.map((assertion) => (
              <article className="state-card" key={assertion.id}>
                <div className="state-card-header">
                  <div>
                    <p className="eyebrow">{assertion.fact_key}</p>
                    <h3>{displayValue(assertion.value, assertion.unit)}</h3>
                  </div>
                  <span className="status">{assertion.status}</span>
                </div>

                <div className="fact-meta-grid">
                  <span>
                    Effective: {assertion.effective_date || "not established"}
                  </span>
                  <span>
                    Derivation: {assertion.derivation_method}{" "}
                    {assertion.derivation_version}
                  </span>
                </div>

                <div className="state-evidence">
                  <strong>Reviewed evidence</strong>
                  {assertion.evidence.map((link) => {
                    const candidate = candidateById.get(link.fact_candidate_id);
                    if (!candidate) {
                      return (
                        <div className="history-row" key={link.fact_candidate_id}>
                          <span>{link.relationship}</span>
                          <span>{link.fact_candidate_id.slice(0, 8)}…</span>
                        </div>
                      );
                    }

                    return (
                      <div className="history-row" key={candidate.id}>
                        <span className="history-relationship">{link.relationship}</span>
                        <span>
                          {displayValue(reviewedValue(candidate), candidate.unit)}
                        </span>
                        <span>{candidate.effective_date || "undated"}</span>
                        <span className="history-source">
                          {candidate.source_kind === "FIELD_VERIFICATION"
                            ? "FIELD · "
                            : "DOC · "}
                          {candidate.source_excerpt}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section>
        <p className="eyebrow">Needs verification</p>
        <h2>Open tasks</h2>
        {openTasks.length === 0 ? (
          <div className="empty-state">
            <strong>No open verification tasks.</strong>
            <p>That means reviewed facts currently have no unresolved Slice 5 conflicts.</p>
          </div>
        ) : (
          <div className="verification-list">
            {openTasks.map((task) => (
              <article className="verification-card" key={task.id}>
                <div className="state-card-header">
                  <div>
                    <p className="eyebrow">{task.reason_code}</p>
                    <h3>{task.fact_key}</h3>
                  </div>
                  <span className="status">{task.status}</span>
                </div>
                <p>{task.reason}</p>
                <p className="verification-instructions">{task.instructions}</p>
                {task.reason_code !== "MISSING_REFERENCED_DOCUMENT" ? (
                  <Link
                    className="button"
                    href={`/projects/${projectId}/verify/${task.id}`}
                  >
                    Open field verification
                  </Link>
                ) : (
                  <span className="status">Resolve by supplying document</span>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {resolvedTasks.length > 0 ? (
        <section>
          <p className="eyebrow">History</p>
          <h2>Resolved verification tasks</h2>
          <div className="verification-list">
            {resolvedTasks.map((task) => (
              <article className="verification-card resolved" key={task.id}>
                <div className="state-card-header">
                  <div>
                    <p className="eyebrow">{task.reason_code}</p>
                    <h3>{task.fact_key}</h3>
                  </div>
                  <span className="status">{task.status}</span>
                </div>
                <p>{task.reason}</p>
                <p>
                  Resolution: {displayValue(task.resolution_value, null)}
                </p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
