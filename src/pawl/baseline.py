"""The baseline file: the committed state the gate ratchets against."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawl.errors import ConfigError

SCHEMA = 1


@dataclass
class SuiteBaseline:
    """Recorded state of one suite."""

    failing_ids: list[str] = field(default_factory=list)
    collected: int = 0
    collected_ids: list[str] = field(default_factory=list)
    skipped_ids: list[str] = field(default_factory=list)
    identity: str = "ids"
    confirmed_orders: int = 1
    order_dependent: list[str] = field(default_factory=list)

    @property
    def failures(self) -> int:
        return len(self.failing_ids)

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "failures": self.failures,
            "failing_ids": sorted(self.failing_ids),
            "collected": self.collected,
            "identity": self.identity,
            "confirmed_orders": self.confirmed_orders,
        }
        if self.identity == "ids":
            data["collected_ids"] = sorted(self.collected_ids)
            data["skipped_ids"] = sorted(self.skipped_ids)
        if self.order_dependent:
            data["order_dependent"] = sorted(self.order_dependent)
        return data


@dataclass
class Quarantine:
    """A failing test excused until ``expires``. Expired entries count again."""

    suite: str
    test_id: str
    reason: str
    expires: str

    def active(self, today: dt.date) -> bool:
        return dt.date.fromisoformat(self.expires) >= today


@dataclass
class Baseline:
    """The whole baseline file."""

    suites: dict[str, SuiteBaseline] = field(default_factory=dict)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    quarantine: list[Quarantine] = field(default_factory=list)
    updated: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "pawl_baseline": SCHEMA,
            "updated": self.updated,
            "suites": {k: v.to_json() for k, v in sorted(self.suites.items())},
            "metrics": {k: v for k, v in sorted(self.metrics.items())},
            "quarantine": [
                {"suite": q.suite, "id": q.test_id, "reason": q.reason, "expires": q.expires}
                for q in sorted(self.quarantine, key=lambda q: (q.suite, q.test_id))
            ],
        }

    def dumps(self) -> str:
        return json.dumps(self.to_json(), indent=2, sort_keys=False) + "\n"

    def active_quarantine(self, suite: str, today: dt.date) -> set[str]:
        return {q.test_id for q in self.quarantine if q.suite == suite and q.active(today)}


def _list_of_str(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"baseline {where}: must be a list of strings")
    return list(value)


def parse_baseline(text: str, source: str = "baseline") -> Baseline:
    """Parse baseline JSON. Any inconsistency is an error (fail closed)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{source}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("pawl_baseline") != SCHEMA:
        raise ConfigError(f"{source}: not a pawl baseline (schema {SCHEMA})")
    suites: dict[str, SuiteBaseline] = {}
    for name, raw in dict(data.get("suites", {})).items():
        if not isinstance(raw, dict):
            raise ConfigError(f"{source}: suite {name} must be an object")
        failing = _list_of_str(raw.get("failing_ids", []), f"{name}.failing_ids")
        if int(raw.get("failures", len(failing))) != len(failing):
            raise ConfigError(
                f"{source}: suite {name} says failures={raw.get('failures')} "
                f"but lists {len(failing)} failing IDs"
            )
        identity = str(raw.get("identity", "ids"))
        collected_ids = _list_of_str(raw.get("collected_ids", []), f"{name}.collected_ids")
        collected = int(raw.get("collected", 0))
        if identity == "ids" and len(collected_ids) != collected:
            raise ConfigError(
                f"{source}: suite {name} says collected={collected} "
                f"but lists {len(collected_ids)} IDs"
            )
        suites[str(name)] = SuiteBaseline(
            failing_ids=failing,
            collected=collected,
            collected_ids=collected_ids,
            skipped_ids=_list_of_str(raw.get("skipped_ids", []), f"{name}.skipped_ids"),
            identity=identity,
            confirmed_orders=int(raw.get("confirmed_orders", 1)),
            order_dependent=_list_of_str(raw.get("order_dependent", []), f"{name}.order_dependent"),
        )
    metrics: dict[str, dict[str, Any]] = {}
    for name, raw in dict(data.get("metrics", {})).items():
        if not isinstance(raw, dict) or not isinstance(raw.get("value"), (int, float)):
            raise ConfigError(f"{source}: metric {name} needs a numeric 'value'")
        if raw.get("direction") not in ("down", "up"):
            raise ConfigError(f"{source}: metric {name} needs direction 'down' or 'up'")
        metrics[str(name)] = dict(raw)
    quarantine = []
    for raw in data.get("quarantine", []):
        try:
            q = Quarantine(
                str(raw["suite"]), str(raw["id"]), str(raw["reason"]), str(raw["expires"])
            )
            dt.date.fromisoformat(q.expires)
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"{source}: invalid quarantine entry {raw!r}") from exc
        quarantine.append(q)
    return Baseline(suites, metrics, quarantine, str(data.get("updated", "")))


def load_baseline(path: Path) -> Baseline:
    if not path.is_file():
        raise ConfigError(f"no baseline at {path}; run 'pawl init' or 'pawl update'")
    return parse_baseline(path.read_text(encoding="utf-8"), str(path.name))


def write_baseline(path: Path, baseline: Baseline) -> None:
    baseline.updated = dt.date.today().isoformat()
    path.write_text(baseline.dumps(), encoding="utf-8")


def stricter(a: Baseline, b: Baseline) -> Baseline:
    """Combine two baselines, keeping the stricter value of every field.

    CI scores a change against the stricter of the base-branch baseline and the
    head baseline, so a branch cannot lower its own bar (the same rule as
    ratchet-gate's --baseline-ref: https://pypi.org/project/ratchet-gate/).
    """
    out = Baseline(updated=b.updated or a.updated)
    for name in set(a.suites) | set(b.suites):
        x, y = a.suites.get(name), b.suites.get(name)
        if x is None or y is None:
            out.suites[name] = x or y  # type: ignore[assignment]
            continue
        out.suites[name] = SuiteBaseline(
            failing_ids=sorted(set(x.failing_ids) & set(y.failing_ids)),
            collected=max(x.collected, y.collected),
            collected_ids=sorted(set(x.collected_ids) | set(y.collected_ids)),
            skipped_ids=sorted(set(x.skipped_ids) & set(y.skipped_ids)),
            identity="ids" if "ids" in (x.identity, y.identity) else "count",
            confirmed_orders=max(x.confirmed_orders, y.confirmed_orders),
            order_dependent=sorted(set(x.order_dependent) & set(y.order_dependent)),
        )
        if out.suites[name].identity == "ids":
            out.suites[name].collected = max(
                out.suites[name].collected, len(out.suites[name].collected_ids)
            )
    for name in set(a.metrics) | set(b.metrics):
        mx, my = a.metrics.get(name), b.metrics.get(name)
        if mx is None or my is None:
            out.metrics[name] = dict(mx or my or {})
            continue
        pick = min if mx.get("direction") == "down" else max
        out.metrics[name] = {
            "value": pick(float(mx["value"]), float(my["value"])),
            "direction": mx["direction"],
        }
    # A quarantine counts only if both sides have it, and then with the earlier expiry.
    in_b = {(q.suite, q.test_id): q for q in b.quarantine}
    out.quarantine = [
        min(q, in_b[(q.suite, q.test_id)], key=lambda x: x.expires)
        for q in a.quarantine
        if (q.suite, q.test_id) in in_b
    ]
    return out


def check_quarantine(
    baseline: Baseline, max_days: int, today: dt.date, source: str = "baseline"
) -> None:
    """Fail closed on a quarantine that runs past ``quarantine_max_days`` from today.

    ``pawl quarantine`` caps the expiry, but the baseline is a JSON file that can
    be edited by hand; an expiry of 2099-12-31 would excuse a test forever.
    """
    limit = today + dt.timedelta(days=max_days)
    for q in baseline.quarantine:
        if dt.date.fromisoformat(q.expires) > limit:
            raise ConfigError(
                f"{source}: quarantine of {q.test_id} in {q.suite} expires {q.expires}, more "
                f"than quarantine_max_days ({max_days}) from today ({today.isoformat()}). "
                "A human shortens or removes it."
            )
