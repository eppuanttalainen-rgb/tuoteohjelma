"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";

type Project = {
  id: string;
  title: string;
};

type Machine = {
  id: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  internal_asset_id: string | null;
};

type SnapshotSummary = {
  id: string;
  machine_id: string;
  snapshot_type: string;
  status: string;
  schema_version: string;
  state_hash: string;
  created_by: string;
  created_at: string;
};

type SnapshotRead = SnapshotSummary & {
  payload: unknown;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ORGANIZATION_ID =
  process.env.NEXT_PUBLIC_DEV_ORGANIZATION_ID ??
  "11111111-1111-1111-1111-111111111111";
const REVIEWER_ID =
  process.env.NEXT_PUBLIC_DEV_REVIEWER_ID ?? "development-engineer";

function machineLabel(machine: Machine) {
  const label =
    [machine.manufacturer, machine.model].filter(Boolean).join(" ") ||
    machine.internal_asset_id ||
    "Unnamed machine";
  return machine.serial_number ? `${label} · ${machine.serial_number}` : label;
}

export default function SnapshotWorkspacePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const headers = useMemo(
    () => ({ "X-Organization-Id": ORGANIZATION_ID }),
    [],
  );

  const [project, setProject] = useState<Project | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [machineId, setMachineId] = useState("");
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<SnapshotRead | null>(null);
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [reportLoadingId, setReportLoadingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reportFrame = useRef<HTMLIFrameElement | null>(null);

  const loadSnapshots = useCallback(
    async (selectedMachineId: string) => {
      if (!selectedMachineId) {
        setSnapshots([]);
        return;
      }

      const response = await fetch(
        `${API_BASE}/api/v1/machines/${selectedMachineId}/snapshots`,
        { headers },
      );
      if (!response.ok) {
        throw new Error(`Snapshot list failed: ${response.status}`);
      }
      setSnapshots((await response.json()) as SnapshotSummary[]);
    },
    [headers],
  );

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const [projectResponse, machinesResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/projects/${projectId}`, { headers }),
        fetch(`${API_BASE}/api/v1/projects/${projectId}/machines`, { headers }),
      ]);

      if (!projectResponse.ok) {
        throw new Error(`Project request failed: ${projectResponse.status}`);
      }
      if (!machinesResponse.ok) {
        throw new Error(`Machine request failed: ${machinesResponse.status}`);
      }

      const projectData = (await projectResponse.json()) as Project;
      const machineData = (await machinesResponse.json()) as Machine[];

      setProject(projectData);
      setMachines(machineData);

      const nextMachineId =
        machineId && machineData.some((machine) => machine.id === machineId)
          ? machineId
          : machineData[0]?.id ?? "";
      setMachineId(nextMachineId);

      await loadSnapshots(nextMachineId);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load snapshot workspace",
      );
    } finally {
      setLoading(false);
    }
  }, [headers, loadSnapshots, machineId, projectId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  async function changeMachine(nextMachineId: string) {
    setMachineId(nextMachineId);
    setSelectedSnapshot(null);
    setReportHtml(null);
    setError(null);
    try {
      await loadSnapshots(nextMachineId);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load snapshots",
      );
    }
  }

  async function createSnapshot() {
    if (!machineId) {
      setError("Choose a machine first.");
      return;
    }

    setCreating(true);
    setError(null);
    setNotice(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/machines/${machineId}/snapshots`,
        {
          method: "POST",
          headers: {
            ...headers,
            "X-Reviewer-Id": REVIEWER_ID,
          },
        },
      );

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(
          payload?.detail || `Snapshot creation failed: ${response.status}`,
        );
      }

      const snapshot = (await response.json()) as SnapshotRead;
      setSelectedSnapshot(snapshot);
      setReportHtml(null);
      setNotice(
        `Snapshot ${snapshot.state_hash.slice(0, 12)}… is frozen and reproducible.`,
      );
      await loadSnapshots(machineId);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not create snapshot",
      );
    } finally {
      setCreating(false);
    }
  }

  async function previewReport(snapshot: SnapshotSummary) {
    setReportLoadingId(snapshot.id);
    setError(null);
    setNotice(null);

    try {
      const [snapshotResponse, reportResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/snapshots/${snapshot.id}`, { headers }),
        fetch(`${API_BASE}/api/v1/snapshots/${snapshot.id}/report`, { headers }),
      ]);

      if (!snapshotResponse.ok) {
        throw new Error(`Snapshot request failed: ${snapshotResponse.status}`);
      }
      if (!reportResponse.ok) {
        throw new Error(`Report request failed: ${reportResponse.status}`);
      }

      setSelectedSnapshot((await snapshotResponse.json()) as SnapshotRead);
      setReportHtml(await reportResponse.text());
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load report",
      );
    } finally {
      setReportLoadingId(null);
    }
  }

  function printReport() {
    reportFrame.current?.contentWindow?.print();
  }

  if (loading && !project) {
    return (
      <main>
        <section>
          <p className="eyebrow">Snapshots</p>
          <h1>Loading report workspace…</h1>
        </section>
      </main>
    );
  }

  const selectedMachine = machines.find((machine) => machine.id === machineId);

  return (
    <main className="report-workspace-main">
      <section>
        <p className="eyebrow">Slice 7 · Immutable baseline</p>
        <h1>{project?.title ?? "Project"} reports</h1>
        <p className="lead">
          Freeze a reproducible reviewed machine-state baseline. Reports are rendered
          from the frozen snapshot, never from later live database changes.
        </p>
        <div className="actions">
          <Link href={`/projects/${projectId}/state`}>← Machine state</Link>
          <span className="status">{snapshots.length} snapshot(s)</span>
        </div>
      </section>

      <section>
        <div className="snapshot-toolbar">
          <label className="field">
            <span>Machine</span>
            <select
              onChange={(event) => void changeMachine(event.target.value)}
              value={machineId}
            >
              {machines.length === 0 ? (
                <option value="">No machines</option>
              ) : null}
              {machines.map((machine) => (
                <option key={machine.id} value={machine.id}>
                  {machineLabel(machine)}
                </option>
              ))}
            </select>
          </label>

          <button
            className="button"
            disabled={creating || !machineId}
            onClick={() => void createSnapshot()}
            type="button"
          >
            {creating ? "Freezing baseline…" : "Create current-state snapshot"}
          </button>
        </div>

        {selectedMachine ? (
          <p className="section-copy">
            Snapshot target: <strong>{machineLabel(selectedMachine)}</strong>
          </p>
        ) : null}

        {notice ? <p className="notice">{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section>
        <p className="eyebrow">Immutable history</p>
        <h2>Snapshots</h2>

        {snapshots.length === 0 ? (
          <div className="empty-state">
            <strong>No snapshot yet.</strong>
            <p>Reconcile reviewed machine state before freezing a baseline.</p>
          </div>
        ) : (
          <div className="snapshot-list">
            {snapshots.map((snapshot) => (
              <article className="snapshot-card" key={snapshot.id}>
                <div>
                  <div className="snapshot-card-header">
                    <strong>{snapshot.status}</strong>
                    <span className="status">schema {snapshot.schema_version}</span>
                  </div>
                  <code className="snapshot-hash">{snapshot.state_hash}</code>
                  <p>
                    Created{" "}
                    {new Date(snapshot.created_at).toLocaleString(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}{" "}
                    by {snapshot.created_by}
                  </p>
                </div>
                <button
                  className="secondary-button"
                  disabled={reportLoadingId === snapshot.id}
                  onClick={() => void previewReport(snapshot)}
                  type="button"
                >
                  {reportLoadingId === snapshot.id
                    ? "Loading report…"
                    : "Preview evidence report"}
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      {selectedSnapshot && reportHtml ? (
        <section>
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Frozen report</p>
              <h2>Machine Current-State Evidence Report</h2>
            </div>
            <button className="button" onClick={printReport} type="button">
              Print / Save as PDF
            </button>
          </div>
          <p className="section-copy">
            Snapshot hash: <code>{selectedSnapshot.state_hash}</code>
          </p>
          <iframe
            className="report-preview"
            ref={reportFrame}
            srcDoc={reportHtml}
            title="Machine Current-State Evidence Report"
          />
        </section>
      ) : null}
    </main>
  );
}
