"""Render JSON reports as Markdown for PR comments and terminals."""

from __future__ import annotations

from typing import Any

ICON = {"pass": "PASS", "fail": "FAIL", "error": "ERROR"}


def _provenance(data: dict[str, Any]) -> list[str]:
    """The same 'where did the gate come from' lines for check and guard."""
    out = []
    if data.get("config_source"):
        out.append(f"Gate definition: `{data['config_source']}`")
    approval = data.get("approval")
    if approval:
        how = f"label `{approval.get('label')}`" if approval.get("source") == "label" else "flag"
        out.append(f"Approved by {how}")
    return [*out, ""] if out else []


def check_markdown(data: dict[str, Any]) -> str:
    out = [f"### Pawl check: {ICON.get(data['status'], data['status'])}", ""]
    out += _provenance(data)
    if data.get("error"):
        out += [f"Error (fail closed): `{data['error']}`", ""]
    if data.get("suites"):
        out += ["| Suite | Failures (baseline) | Collected (floor) | Orders |", "|---|---|---|---|"]
        for s in data["suites"]:
            out.append(
                f"| {s['name']} | {s['failures']} ({s['baseline_failures']}) | "
                f"{s['collected']} ({s['baseline_collected']}) | {', '.join(s['orders'])} |"
            )
        out.append("")
    if data.get("metrics"):
        out += ["| Metric | Value | Baseline | Direction |", "|---|---|---|---|"]
        for m in data["metrics"]:
            out.append(f"| {m['name']} | {m['value']:g} | {m['baseline']:g} | {m['direction']} |")
        out.append("")
    for p in data.get("problems", []):
        out.append(f"- **{p['code']}** `{p['subject']}`: {p['message']}")
        for i in p.get("ids", [])[:10]:
            verdict = data.get("isolation", {}).get(p["subject"], {}).get(i)
            out.append(f"  - `{i}`" + (f" ({verdict})" if verdict else ""))
        if p.get("ids_total", 0) > 10:
            out.append(f"  - ...and {p['ids_total'] - 10} more")
    for n in data.get("notes", []):
        out.append(f"- Note: {n}")
    if data.get("next_steps"):
        out += ["", "**Next steps**"] + [f"{n}. {s}" for n, s in enumerate(data["next_steps"], 1)]
    return "\n".join(out) + "\n"


def guard_markdown(data: dict[str, Any]) -> str:
    out = [f"### Pawl guard: {ICON.get(data['status'], data['status'])} (base {data['base']})", ""]
    out += _provenance(data)
    if data.get("approved"):
        out += ["Approved by label or flag. Blocking findings are listed for the record.", ""]
    shown = [f for f in data["findings"] if f["severity"] != "info"]
    if not shown:
        out.append("No tampering found.")
    for f in shown:
        out.append(f"- **{f['rule']}** ({f['severity']}) `{f['path']}`: {f['message']}")
        for i in f.get("ids", [])[:10]:
            out.append(f"  - `{i}`")
    for n in data.get("notes", []):
        out.append(f"- Note: {n}")
    return "\n".join(out) + "\n"
