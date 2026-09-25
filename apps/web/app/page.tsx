const workflow = [
  "Upload legacy evidence",
  "Reconstruct machine facts",
  "Resolve conflicts and unknowns",
  "Verify the real machine in the field",
];

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">Slice 0 · Foundation</p>
        <h1>Machine Compliance Intelligence</h1>
        <p className="lead">
          Turn fragmented legacy machine documentation into a traceable current-state record
          before retrofit design begins.
        </p>
        <div className="status">Prototype foundation active</div>
      </section>

      <section>
        <h2>Core workflow</h2>
        <ol className="workflow">
          {workflow.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="principle">
        <h2>Evidence first</h2>
        <p>
          AI proposes machine facts. Engineers confirm them. Important facts must retain a
          traceable source.
        </p>
      </section>
    </main>
  );
}
