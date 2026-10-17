from __future__ import annotations

import html


def render(trend_rows: list[dict[str, object]], registry_rows: list[dict[str, str]]) -> str:
    parts = [
        "<h1>pawl</h1>",
        f"<p>{len(trend_rows)} runs, {len(registry_rows)} honest negatives</p>",
        "<table><tr><th>when</th><th>kind</th><th>status</th></tr>",
    ]
    for row in trend_rows[-50:]:
        when = html.escape(str(row.get("generated_at", "")))
        kind = html.escape(str(row.get("kind", "")))
        status = html.escape(str(row.get("status", "")))
        parts.append(f"<tr><td>{when}</td><td>{kind}</td><td>{status}</td></tr>")
    parts.append("</table><ul>")
    for row in registry_rows:
        parts.append(f"<li>{html.escape(str(row.get('message', '')))}</li>")
    parts.append("</ul>")
    return "<!doctype html><meta charset=utf-8>" + "".join(parts)
