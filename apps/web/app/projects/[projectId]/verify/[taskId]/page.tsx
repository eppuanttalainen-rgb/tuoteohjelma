"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

type Project = {
  id: string;
  title: string;
};

type VerificationTask = {
  id: string;
  project_id: string;
  machine_id: string;
  fact_key: string;
  reason_code: string;
  reason: string;
  instructions: string;
  status: string;
  resolution_value: unknown | null;
};

type VerificationResult = {
  id: string;
  observed_value: unknown;
  unit: string | null;
  note: string | null;
  photo_reference: string | null;
  verified_by: string;
  verified_at: string;
};

type SubmissionResult = {
  verification: VerificationResult;
  created_fact_candidate_id: string;
  state_assertion_id: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ORGANIZATION_ID =
  process.env.NEXT_PUBLIC_DEV_ORGANIZATION_ID ??
  "11111111-1111-1111-1111-111111111111";
const REVIEWER_ID =
  process.env.NEXT_PUBLIC_DEV_REVIEWER_ID ?? "development-engineer";

function displayValue(value: unknown, unit: string | null) {
  if (value === null || value === undefined) return "Not recorded";
  const rendered =
    typeof value === "string" || typeof value === "number"
      ? String(value)
      : JSON.stringify(value);
  return unit ? `${rendered} ${unit}` : rendered;
}

export default function FieldVerificationPage() {
  const params = useParams<{ projectId: string; taskId: string }>();
  const projectId = params.projectId;
  const taskId = params.taskId;

  const headers = useMemo(
    () => ({ "X-Organization-Id": ORGANIZATION_ID }),
    [],
  );

  const [project, setProject] = useState<Project | null>(null);
  const [task, setTask] = useState<VerificationTask | null>(null);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [observedValue, setObservedValue] = useState("");
  const [unit, setUnit] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectResponse, taskResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/projects/${projectId}`, { headers }),
        fetch(`${API_BASE}/api/v1/verification-tasks/${taskId}`, { headers }),
      ]);

      if (!projectResponse.ok) {
        throw new Error(`Project request failed: ${projectResponse.status}`);
      }
      if (!taskResponse.ok) {
        throw new Error(`Verification task request failed: ${taskResponse.status}`);
      }

      const projectData = (await projectResponse.json()) as Project;
      const taskData = (await taskResponse.json()) as VerificationTask;

      setProject(projectData);
      setTask(taskData);

      const resultResponse = await fetch(
        `${API_BASE}/api/v1/verification-tasks/${taskId}/result`,
        { headers },
      );
      if (resultResponse.ok) {
        setResult((await resultResponse.json()) as VerificationResult);
      } else if (resultResponse.status === 404) {
        setResult(null);
      } else {
        throw new Error(
          `Verification result request failed: ${resultResponse.status}`,
        );
      }

      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load field verification task",
      );
    } finally {
      setLoading(false);
    }
  }, [headers, projectId, taskId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function submitVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!observedValue.trim()) {
      setError("Record the observed value before submitting.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setNotice(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/verification-tasks/${taskId}/verify`,
        {
          method: "POST",
          headers: {
            ...headers,
            "Content-Type": "application/json",
            "X-Reviewer-Id": REVIEWER_ID,
          },
          body: JSON.stringify({
            observed_value: observedValue.trim(),
            unit: unit.trim() || null,
            note: note.trim() || null,
          }),
        },
      );

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(
          payload?.detail || `Verification submission failed: ${response.status}`,
        );
      }

      const submission = (await response.json()) as SubmissionResult;
      setResult(submission.verification);
      setNotice(
        submission.state_assertion_id
          ? "Field observation stored, reviewed, and reconciled into machine state."
          : "Field observation stored and reviewed.",
      );
      await loadData();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not submit field verification",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !task) {
    return (
      <main className="field-mobile-main">
        <section>
          <p className="eyebrow">Field verification</p>
          <h1>Loading task…</h1>
        </section>
      </main>
    );
  }

  const documentOnly = task?.reason_code === "MISSING_REFERENCED_DOCUMENT";

  return (
    <main className="field-mobile-main">
      <section className="field-task-hero">
        <p className="eyebrow">Slice 6 · Field verification</p>
        <h1>{task?.fact_key ?? "Verification task"}</h1>
        <p className="lead">{task?.reason}</p>
        <div className="actions">
          <Link href={`/projects/${projectId}/state`}>← Machine state</Link>
          <span className="status">{task?.status ?? "UNKNOWN"}</span>
          <span className="status">{task?.reason_code}</span>
        </div>
      </section>

      <section>
        <p className="eyebrow">Project</p>
        <h2>{project?.title ?? "Project"}</h2>
        <div className="field-instruction">
          <strong>What to verify</strong>
          <p>{task?.instructions}</p>
        </div>
      </section>

      {documentOnly ? (
        <section>
          <h2>Document evidence required</h2>
          <p className="section-copy">
            This task cannot be resolved by a field observation. Supply the referenced
            document in the Evidence workspace so the evidence chain stays correct.
          </p>
          <Link className="button" href={`/projects/${projectId}`}>
            Open Evidence workspace
          </Link>
        </section>
      ) : result ? (
        <section>
          <p className="eyebrow">Verified observation</p>
          <h2>{displayValue(result.observed_value, result.unit)}</h2>
          <div className="field-result-grid">
            <span>Verified by: {result.verified_by}</span>
            <span>
              Verified:{" "}
              {new Date(result.verified_at).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </span>
            <span>Note: {result.note || "No note"}</span>
          </div>
          <div className="actions">
            <Link className="button" href={`/projects/${projectId}/state`}>
              View updated machine state
            </Link>
          </div>
        </section>
      ) : (
        <section>
          <p className="eyebrow">Record observation</p>
          <h2>Field result</h2>
          <form className="field-verification-form" onSubmit={submitVerification}>
            <label className="field field-wide">
              <span>Observed value</span>
              <input
                autoComplete="off"
                inputMode="text"
                onChange={(event) => setObservedValue(event.target.value)}
                placeholder="e.g. AZM 161"
                required
                value={observedValue}
              />
            </label>

            <label className="field">
              <span>Unit (optional)</span>
              <input
                autoComplete="off"
                onChange={(event) => setUnit(event.target.value)}
                placeholder="e.g. kW"
                value={unit}
              />
            </label>

            <label className="field field-wide">
              <span>Engineer note (optional)</span>
              <textarea
                onChange={(event) => setNote(event.target.value)}
                placeholder="Where and how was the value verified?"
                rows={5}
                value={note}
              />
            </label>

            <div className="field-photo-placeholder field-wide">
              <strong>Photo evidence</strong>
              <p>
                Photo storage is intentionally disabled until Security Gate #4 is
                complete. Do not upload real customer photos to this prototype.
              </p>
            </div>

            <button className="button field-submit" disabled={submitting} type="submit">
              {submitting ? "Saving verification…" : "Confirm field observation"}
            </button>
          </form>
        </section>
      )}

      {notice ? <p className="notice">{notice}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
