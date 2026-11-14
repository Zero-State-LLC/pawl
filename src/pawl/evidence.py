"""Bound untrusted evidence before decoding or allocating parser trees."""

from __future__ import annotations

import json
import os
import stat
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pawl.errors import ParseError
from pawl.runner import ExecutionLimits


class ReportError(ParseError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def bounded_text(text: str, limits: ExecutionLimits) -> None:
    limits.validate()
    if len(text.encode("utf-8")) > limits.max_report_bytes:
        raise ReportError("REPORT_LIMIT", "report exceeds byte limit")


def read_report(path: Path, limits: ExecutionLimits) -> bytes:
    """Read one verified descriptor. Never follow links, including parent links."""
    limits.validate()
    absolute = Path(os.path.abspath(path))
    fd = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.stat(absolute.name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            raise ParseError("report must be a regular file, not a symlink")
        if not stat.S_ISREG(info.st_mode):
            raise ParseError("report must be a regular file")
        child = os.open(absolute.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        os.close(fd)
        fd = child
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ParseError("report must be a regular file")
        if before.st_nlink != 1:
            raise ParseError("report must not be a hard link")
        if (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
            raise ParseError("report changed while opening")
        if before.st_size > limits.max_report_bytes:
            raise ReportError("REPORT_LIMIT", "report exceeds byte limit")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(fd, min(65536, limits.max_report_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > limits.max_report_bytes:
                raise ReportError("REPORT_LIMIT", "report exceeds byte limit")
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or after.st_nlink != 1:
            raise ParseError("report changed while reading")
        return b"".join(chunks)
    except OSError as exc:
        raise ParseError(f"report not written or unsafe path: {path}") from exc
    finally:
        os.close(fd)


def load_json(text: str, limits: ExecutionLimits) -> Any:
    bounded_text(text, limits)
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > limits.max_parse_depth:
                raise ReportError("PARSE_LIMIT", "JSON nesting exceeds limit")
        elif char in "]}":
            depth -= 1

    def constant(value: str) -> Any:
        raise ParseError(f"nonfinite JSON constant: {value}")

    try:
        return json.loads(text, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        raise ParseError("report is not valid JSON") from exc


class BoundedXML(ET.TreeBuilder):
    """Enforce budgets before TreeBuilder allocates each element."""

    def __init__(self, limits: ExecutionLimits) -> None:
        super().__init__()
        self.limits = limits
        self.depth = self.records = self.elements = 0

    def start(self, tag: str, attrs: dict[str, str]) -> ET.Element:
        self.depth += 1
        self.elements += 1
        self.records += tag == "testcase"
        if self.depth > self.limits.max_parse_depth:
            raise ReportError("PARSE_LIMIT", "XML nesting exceeds limit")
        if self.records > self.limits.max_test_records:
            raise ReportError("REPORT_LIMIT", "test record count exceeds limit")
        if self.elements > self.limits.max_test_records * 8 + 1024:
            raise ReportError("PARSE_LIMIT", "XML element count exceeds limit")
        return super().start(tag, attrs)

    def end(self, tag: str) -> ET.Element:
        self.depth -= 1
        return super().end(tag)

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ParseError("JUnit DTD declarations are not allowed")
