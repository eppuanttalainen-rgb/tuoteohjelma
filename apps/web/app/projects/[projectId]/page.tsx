"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Project = {
  id: string;
  title: string;
  customer_reference: string | null;
  objective: string | null;
  jurisdiction: string | null;
  status: string;
};

type Machine = {
  id: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  internal_asset_id: string | null;
  machine_type: string | null;
  status: string;
};

type EvidenceDocument = {
  id: string;
  machine_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  document_type: string | null;
  revision: string | null;
  document_date: string | null;
  language: string | null;
  sha256: string;
  processing_status: string;
  created_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ORGANIZATION_ID =
  process.env.NEXT_PUBLIC_DEV_ORGANIZATION_ID ??
  "11111111-1111-1111-1111-111111111111";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function machineLabel(machine: Machine) {
  const primary =
    [machine.manufacturer, machine.model].filter(Boolean).join(" ") ||
    machine.internal_asset_id ||
    machine.machine_type ||
    "Unnamed machine";

  return machine.serial_number ? `${primary} · ${machine.serial_number}` : primary;
}

export default function ProjectWorkspacePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [project, setProject] = useState<Project | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [documents, setDocuments] = useState<EvidenceDocument[]>([]);
  const [selectedMachineId, setSelectedMachineId] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const headers = { "X-Organization-Id": ORGANIZATION_ID };

  const loadWorkspace = useCallback(async () => {
    setLoading(true);

    try {
      const [projectResponse, machinesResponse, documentsResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/projects/${projectId}`, { headers }),
        fetch(`${API_BASE}/api/v1/projects/${projectId}/machines`, { headers }),
        fetch(`${API_BASE}/api/v1/projects/${projectId}/documents`, { headers }),
      ]);

      if (!projectResponse.ok) {
        throw new Error(`Project request failed: ${projectResponse.status}`);
      }
      if (!machinesResponse.ok) {
        throw new Error(`Machines request failed: ${machinesResponse.status}`);
      }
      if (!documentsResponse.ok) {
        throw new Error(`Evidence request failed: ${documentsResponse.status}`);
      }

      setProject((await projectResponse.json()) as Project);
      setMachines((await machinesResponse.json()) as Machine[]);
      setDocuments((await documentsResponse.json()) as EvidenceDocument[]);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not load project workspace",
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  async function uploadEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError("Choose a PDF file first.");
      return;
    }

    setUploading(true);
    setError(null);
    setNotice(null);

    const body = new FormData();
    body.append("file", selectedFile);
    if (selectedMachineId) {
      body.append("machine_id", selectedMachineId);
    }

    try {
      const response = await fetch(`${API_BASE}/api/v1/projects/${projectId}/documents`, {
        method: "POST",
        headers,
        body,
      });

      if (response.status === 409) {
        const duplicate = (await response.json()) as {
          detail?: { existing_document_id?: string; message?: string } | string;
        };
        const existingId =
          typeof duplicate.detail === "object"
            ? duplicate.detail.existing_document_id
            : undefined;
        throw new Error(
          existingId
            ? `This evidence already exists in the project (${existingId.slice(0, 8)}…).`
            : "This evidence already exists in the project.",
        );
      }

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(payload?.detail || `Upload failed: ${response.status}`);
      }

      setSelectedFile(null);
      const input = document.getElementById("evidence-file") as HTMLInputElement | null;
      if (input) input.value = "";
      setNotice("Evidence stored. Automated extraction is intentionally not active yet.");
      await loadWorkspace();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not upload evidence",
      );
    } finally {
      setUploading(false);
    }
  }

  if (loading && !project) {
    return (
      <main>
        <section>
          <p className="eyebrow">Evidence workspace</p>
          <h1>Loading project…</h1>
        </section>
      </main>
    );
  }

  return (
    <main>
      <section>
        <p className="eyebrow">Slice 2 · Evidence workspace</p>
        <h1>{project?.title ?? "Project"}</h1>
        <p className="lead">
          {project?.objective ||
            "Collect the evidence needed to reconstruct the machine's current state."}
        </p>
        <div className="actions">
          <Link href="/projects">← Projects</Link>
          <span className="status">{project?.jurisdiction || "No jurisdiction"}</span>
          <span className="status">{documents.length} evidence file(s)</span>
        </div>
      </section>

      <section>
        <h2>Add evidence</h2>
        <p className="section-copy">
          Slice 2 stores and inventories PDF evidence only. It does not yet extract technical
          facts or make compliance conclusions.
        </p>

        <form className="evidence-form" onSubmit={uploadEvidence}>
          <label className="field">
            <span>Associate with machine (optional)</span>
            <select
              value={selectedMachineId}
              onChange={(event) => setSelectedMachineId(event.target.value)}
            >
              <option value="">Project-level evidence</option>
              {machines.map((machine) => (
                <option key={machine.id} value={machine.id}>
                  {machineLabel(machine)}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>PDF evidence</span>
            <input
              accept="application/pdf,.pdf"
              id="evidence-file"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>

          <button className="button" disabled={uploading || !selectedFile} type="submit">
            {uploading ? "Uploading…" : "Store evidence"}
          </button>
        </form>

        {notice ? <p className="notice">{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Project evidence</p>
            <h2>Inventory</h2>
          </div>
          <button className="secondary-button" onClick={() => void loadWorkspace()} type="button">
            Refresh
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="empty-state">
            <strong>No evidence stored yet.</strong>
            <p>Use a synthetic or explicitly non-sensitive PDF while Security Gate #4 is open.</p>
          </div>
        ) : (
          <div className="evidence-list">
            {documents.map((item) => {
              const machine = machines.find((candidate) => candidate.id === item.machine_id);

              return (
                <article className="evidence-card" key={item.id}>
                  <div className="evidence-main">
                    <div className="evidence-title-row">
                      <h3>{item.filename}</h3>
                      <span className="status">{item.processing_status}</span>
                    </div>
                    <p>
                      {machine ? machineLabel(machine) : "Project-level evidence"} ·{" "}
                      {formatBytes(item.size_bytes)}
                    </p>
                    <code className="hash">SHA-256 {item.sha256}</code>
                  </div>
                  <div className="evidence-meta">
                    <span>
                      {new Date(item.created_at).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </span>
                    <span>{item.id.slice(0, 8)}…</span>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <h2>Machines in this project</h2>
        {machines.length === 0 ? (
          <p>No machines have been added yet. Evidence can still be stored at project level.</p>
        ) : (
          <div className="machine-grid">
            {machines.map((machine) => (
              <article className="machine-card" key={machine.id}>
                <h3>{machineLabel(machine)}</h3>
                <p>{machine.machine_type || "Machine type not recorded"}</p>
                <span className="status">{machine.status}</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
