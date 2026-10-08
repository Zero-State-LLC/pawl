from __future__ import annotations

import pytest

from pawl.config import MetricConfig
from pawl.errors import ParseError
from pawl.metrics import extract


def m(spec: str) -> MetricConfig:
    return MetricConfig("m", ("x",), "down", spec)


def test_extractors() -> None:
    assert extract(m("count-lines"), "a\n\nb\n", "") == 2
    assert extract(m("count-regex:^E\\d+"), "E1 x\nW2 y\nE3 z", "") == 2
    assert extract(m(r"regex:TOTAL.*?(\d+)%"), "TOTAL    100   20    80%", "") == 80
    assert extract(m("regex:Found (\\d+) error"), "", "Found 7 errors") == 7
    assert extract(m("json:summary.errors"), '{"summary": {"errors": 4}}', "") == 4
    assert extract(m("json:items.length()"), '{"items": [1, 2, 3]}', "") == 3


@pytest.mark.parametrize(
    ("spec", "out"),
    [
        ("regex:nothing (\\d+)", "zzz"),
        ("json:a.b", '{"a": {}}'),
        ("json:a", "not json"),
        ("json:a", '{"a": "str"}'),
    ],
)
def test_extract_fails_closed(spec: str, out: str) -> None:
    with pytest.raises(ParseError):
        extract(m(spec), out, "")
