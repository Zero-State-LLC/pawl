"""Generic numeric metrics: lint counts, type errors, coverage, architecture violations."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pawl.config import MetricConfig
from pawl.errors import ParseError
from pawl.runner import run


def extract(metric: MetricConfig, stdout: str, stderr: str) -> float:
    """Extract one number from command output.

    ``regex:`` and ``json:`` fail when nothing matches. The count modes return 0
    for output with no matching lines, which is why ``measure`` checks the exit
    code first.
    """
    spec = metric.extract
    text = stdout + "\n" + stderr
    if spec == "count-lines":
        return float(sum(1 for line in stdout.splitlines() if line.strip()))
    if spec.startswith("count-regex:"):
        return float(len(re.findall(spec.split(":", 1)[1], text, flags=re.MULTILINE)))
    if spec.startswith("regex:"):
        pattern = spec.split(":", 1)[1]
        matches = re.findall(pattern, text, flags=re.MULTILINE)
        if not matches:
            raise ParseError(f"metric {metric.name}: pattern {pattern!r} matched nothing")
        last = matches[-1]
        value = last if isinstance(last, str) else last[0]
        try:
            return float(value)
        except ValueError as exc:
            raise ParseError(f"metric {metric.name}: {value!r} is not a number") from exc
    if spec.startswith("json:"):
        try:
            node: object = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ParseError(f"metric {metric.name}: output is not JSON") from exc
        for key in spec.split(":", 1)[1].split("."):
            if key == "length()" and isinstance(node, list):
                node = len(node)
            elif isinstance(node, dict) and key in node:
                node = node[key]
            elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
                node = node[int(key)]
            else:
                raise ParseError(f"metric {metric.name}: JSON path {spec} not found")
        if not isinstance(node, (int, float)) or isinstance(node, bool):
            raise ParseError(f"metric {metric.name}: JSON value is not a number")
        return float(node)
    raise ParseError(f"metric {metric.name}: unknown extract {spec}")


def measure(metric: MetricConfig, root: Path) -> float:
    """Run the metric command and extract its value. Fails closed.

    A command that exits with a code outside ``ok_exit_codes`` did not measure
    anything, even if its output happens to parse (a crashed linter prints no
    findings, which a count would read as 0).
    """
    done = run(metric.command, root / metric.cwd, metric.timeout)
    if done.returncode not in metric.ok_exit_codes:
        allowed = ", ".join(str(c) for c in metric.ok_exit_codes)
        raise ParseError(
            f"metric {metric.name}: command exited {done.returncode} (allowed: {allowed}); "
            f"the metric was not measured:\n{done.tail()}"
        )
    return extract(metric, done.stdout, done.stderr)


def metric_delta(metric: MetricConfig, value: float, baseline: float) -> str:
    """Classify ``value`` against ``baseline``: 'worse', 'better', or 'same'.

    Differences within ``metric.tolerance`` count as the same, so float noise
    (coverage 85.79 vs 85.78) neither fails the gate nor forces a baseline update.
    """
    diff = value - baseline if metric.direction == "up" else baseline - value
    if diff < -metric.tolerance:
        return "worse"
    if diff > metric.tolerance:
        return "better"
    return "same"
