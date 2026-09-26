import html
import json
from typing import Any

from app.models import Snapshot


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return html.escape(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return html.escape(str(value))


def _value_with_unit(value: Any, unit: str | None) -> str:
    rendered = _escape(value)
    return f"{rendered} {html.escape(unit)}" if unit else rendered


def render_machine_evidence_report(snapshot: Snapshot) -> str:
    payload = snapshot.payload
    project = payload["project"]
    machine = payload["machine"]
    assertions = payload["state_assertions"]
    tasks = payload["verification_tasks"]
    documents = payload["documents"]

    current_rows = []
    history_rows = []
    trace_rows = []

    for assertion in assertions:
        current_rows.append(
            "<tr>"
            f"<td>{_escape(assertion['fact_key'])}</td>"
            f"<td>{_value_with_unit(assertion['value'], assertion['unit'])}</td>"
            f"<td>{_escape(assertion['status'])}</td>"
            f"<td>{_escape(assertion['effective_date'])}</td>"
            "</tr>"
        )
        for evidence in assertion["evidence"]:
            if evidence["relationship"] == "SUPERSEDED":
                history_rows.append(
                    "<tr>"
                    f"<td>{_escape(assertion['fact_key'])}</td>"
                    f"<td>{_value_with_unit(evidence['value'], evidence['unit'])}</td>"
                    f"<td>{_escape(evidence['effective_date'])}</td>"
                    f"<td>{_escape(evidence['source_kind'])}</td>"
                    f"<td>{_escape(evidence['source_excerpt'])}</td>"
                    "</tr>"
                )
            trace_rows.append(
                "<tr>"
                f"<td>{_escape(assertion['fact_key'])}</td>"
                f"<td>{_escape(evidence['relationship'])}</td>"
                f"<td>{_escape(evidence['candidate_id'])}</td>"
                f"<td>{_escape(evidence['source_kind'])}</td>"
                f"<td>{_escape(evidence['document_id'] or evidence['verification_result_id'])}</td>"
                f"<td>{_escape(evidence['source_excerpt'])}</td>"
                "</tr>"
            )

    unresolved_rows = [
        "<tr>"
        f"<td>{_escape(assertion['fact_key'])}</td>"
        f"<td>{_escape(assertion['status'])}</td>"
        f"<td>{_value_with_unit(assertion['value'], assertion['unit'])}</td>"
        "</tr>"
        for assertion in assertions
        if assertion["status"] in {"DISPUTED", "UNKNOWN"}
    ]

    open_task_rows = [
        "<tr>"
        f"<td>{_escape(task['fact_key'])}</td>"
        f"<td>{_escape(task['reason_code'])}</td>"
        f"<td>{_escape(task['reason'])}</td>"
        f"<td>{_escape(task['instructions'])}</td>"
        "</tr>"
        for task in tasks
        if task["status"] == "OPEN"
    ]

    verification_rows = []
    for task in tasks:
        if task["result"] is None:
            continue
        result = task["result"]
        verification_rows.append(
            "<tr>"
            f"<td>{_escape(task['fact_key'])}</td>"
            f"<td>{_value_with_unit(result['observed_value'], result['unit'])}</td>"
            f"<td>{_escape(result['verified_by'])}</td>"
            f"<td>{_escape(result['verified_at'])}</td>"
            f"<td>{_escape(result['note'])}</td>"
            "</tr>"
        )

    document_rows = [
        "<tr>"
        f"<td>{_escape(document['filename'])}</td>"
        f"<td>{_escape(document['processing_status'])}</td>"
        f"<td><code>{_escape(document['sha256'])}</code></td>"
        f"<td>{_escape(document['machine_id'] or 'project-level')}</td>"
        "</tr>"
        for document in documents
    ]

    def table_or_empty(headers: list[str], rows: list[str], empty: str) -> str:
        if not rows:
            return f'<p class="empty">{html.escape(empty)}</p>'
        header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        return (
            '<div class="table-wrap"><table><thead><tr>'
            + header_html
            + "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Machine Current-State Evidence Report</title>
<style>
  :root {{ font-family: Arial, Helvetica, sans-serif; color: #17191c; }}
  body {{ margin: 0; background: #f3f5f7; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px 64px; }}
  section {{ background: #fff; border: 1px solid #dfe3e8; border-radius: 12px;
             padding: 24px; margin: 0 0 18px; break-inside: avoid; }}
  h1 {{ margin: 4px 0 12px; font-size: 34px; }}
  h2 {{ margin: 0 0 14px; font-size: 21px; }}
  p {{ line-height: 1.55; }}
  .eyebrow {{ color: #5b6470; font-size: 12px; font-weight: 700;
              letter-spacing: .08em; text-transform: uppercase; }}
  .meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
           gap: 10px 24px; }}
  .hash {{ overflow-wrap: anywhere; font-family: monospace; }}
  .warning {{ border-left: 4px solid #6d7680; padding-left: 14px; }}
  .empty {{ color: #67717d; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border-bottom: 1px solid #e6e9ed; padding: 9px; text-align: left;
            vertical-align: top; }}
  th {{ background: #f7f8fa; }}
  code {{ font-size: 11px; overflow-wrap: anywhere; }}
  @media print {{
    body {{ background: #fff; }}
    main {{ max-width: none; padding: 0; }}
    section {{ border: 0; border-radius: 0; padding: 12px 0; }}
  }}
</style>
</head>
<body>
<main>
<section>
  <p class="eyebrow">Machine Current-State Evidence Report</p>
  <h1>{_escape(machine['manufacturer'])} {_escape(machine['model'])}</h1>
  <div class="meta">
    <span><strong>Project:</strong> {_escape(project['title'])}</span>
    <span><strong>Serial:</strong> {_escape(machine['serial_number'])}</span>
    <span><strong>Asset ID:</strong> {_escape(machine['internal_asset_id'])}</span>
    <span><strong>Jurisdiction context:</strong> {_escape(project['jurisdiction'])}</span>
    <span><strong>Snapshot status:</strong> {_escape(snapshot.status)}</span>
    <span><strong>Schema:</strong> {_escape(snapshot.schema_version)}</span>
  </div>
  <p><strong>State hash:</strong> <span class="hash">{_escape(snapshot.state_hash)}</span></p>
  <p><strong>Snapshot created:</strong> {_escape(snapshot.created_at.isoformat())}
     by {_escape(snapshot.created_by)}</p>
</section>

<section class="warning">
  <strong>Evidence report — not a compliance certificate.</strong>
  <p>This report records reviewed technical evidence and the reconstructed machine state
  frozen in this snapshot. It does not certify CE conformity, legal compliance, or machine
  safety and does not replace a qualified engineering or legal assessment.</p>
</section>

<section>
  <h2>Current reviewed machine state</h2>
  {table_or_empty(["Fact", "Value", "Status", "Effective"], current_rows, "No state assertions.")}
</section>

<section>
  <h2>Historical / superseded evidence</h2>
  {table_or_empty(["Fact", "Historical value", "Effective", "Source", "Excerpt"], history_rows, "No superseded values.")}
</section>

<section>
  <h2>Disputed / unknown state</h2>
  {table_or_empty(["Fact", "Status", "Value"], unresolved_rows, "No disputed or unknown state in this snapshot.")}
</section>

<section>
  <h2>Open verification tasks</h2>
  {table_or_empty(["Fact", "Reason", "Why", "Instructions"], open_task_rows, "No open verification tasks.")}
</section>

<section>
  <h2>Verification history</h2>
  {table_or_empty(["Fact", "Observed value", "Verified by", "Verified at", "Note"], verification_rows, "No field-verification results.")}
</section>

<section>
  <h2>Document inventory</h2>
  {table_or_empty(["File", "State", "SHA-256", "Scope"], document_rows, "No documents captured.")}
</section>

<section>
  <h2>Traceability appendix</h2>
  {table_or_empty(["Fact", "Relationship", "Candidate", "Source type", "Source", "Excerpt"], trace_rows, "No assertion evidence.")}
</section>
</main>
</body>
</html>"""
