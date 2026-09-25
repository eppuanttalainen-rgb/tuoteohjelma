"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Project = {
  id: string;
  title: string;
  customer_reference: string | null;
  objective: string | null;
  jurisdiction: string | null;
  status: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ORGANIZATION_ID =
  process.env.NEXT_PUBLIC_DEV_ORGANIZATION_ID ??
  "11111111-1111-1111-1111-111111111111";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [title, setTitle] = useState("");
  const [objective, setObjective] = useState("");
  const [jurisdiction, setJurisdiction] = useState("EU");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/projects`, {
        headers: { "X-Organization-Id": ORGANIZATION_ID },
      });

      if (!response.ok) {
        throw new Error(`Projects request failed: ${response.status}`);
      }

      setProjects((await response.json()) as Project[]);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not load projects",
      );
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;

    setSaving(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/v1/projects`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Organization-Id": ORGANIZATION_ID,
        },
        body: JSON.stringify({
          title: title.trim(),
          objective: objective.trim() || null,
          jurisdiction: jurisdiction.trim() || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Create project failed: ${response.status}`);
      }

      setTitle("");
      setObjective("");
      await loadProjects();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not create project",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main>
      <section>
        <p className="eyebrow">Development tenant</p>
        <h1>Projects</h1>
        <p className="lead">
          The temporary organization header is only a development boundary. Real authentication
          and organization membership come later.
        </p>
        <Link href="/">← Home</Link>
      </section>

      <section>
        <h2>Create project</h2>
        <form className="form-grid" onSubmit={createProject}>
          <label className="field">
            <span>Project title</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="CV-204 retrofit"
              required
            />
          </label>

          <label className="field">
            <span>Jurisdiction</span>
            <input
              value={jurisdiction}
              onChange={(event) => setJurisdiction(event.target.value)}
              placeholder="EU"
            />
          </label>

          <label className="field field-wide">
            <span>Objective</span>
            <textarea
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Reconstruct current state before retrofit design"
              rows={4}
            />
          </label>

          <button className="button" disabled={saving} type="submit">
            {saving ? "Creating…" : "Create project"}
          </button>
        </form>

        {error ? <p className="error">{error}</p> : null}
      </section>

      <section>
        <h2>Current projects</h2>
        {projects.length === 0 ? (
          <p>No projects yet.</p>
        ) : (
          <div className="project-list">
            {projects.map((project) => (
              <article className="project-card" key={project.id}>
                <div>
                  <h3>{project.title}</h3>
                  <p>{project.objective || "No objective recorded yet."}</p>
                </div>
                <div className="project-meta">
                  <span>{project.jurisdiction || "No jurisdiction"}</span>
                  <span>{project.status}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
