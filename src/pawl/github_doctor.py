"""Read-only GitHub observations with conservative control assessment."""

from __future__ import annotations

import http.client
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from pawl.errors import PawlError
from pawl.evidence import load_json
from pawl.runner import ExecutionLimits

HOST = "api.github.com"
LIMIT = 1048576
LIMITS = ExecutionLimits(max_report_bytes=LIMIT, max_parse_depth=64)
CONTROLS = (
    "independent_review",
    "code_owner_review",
    "last_push_review",
    "current_base_checks",
    "release_controls",
)


@dataclass(frozen=True)
class Response:
    data: Any = None
    problem: str = ""
    paginated: bool = False


@dataclass(frozen=True)
class Observation:
    id: str
    status: str
    message: str
    source: str


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def fetch(path: str, token: str) -> Response:
    """Fixed TLS host, GET only, no redirects/proxies, bounded body, no raw errors."""
    if not path.startswith("/repos/") or "\r" in path or "\n" in path:
        return Response(problem="Invalid API path.")
    if not token or len(token) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        return Response(problem="Credential is missing or invalid.")
    connection = http.client.HTTPSConnection(HOST, timeout=5)
    started = time.monotonic()
    try:
        connection.request(
            "GET",
            path,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "pawl-doctor",
                "Accept-Encoding": "identity",
            },
        )
        reply = connection.getresponse()
        if reply.status != 200:
            return Response(problem=f"GitHub returned HTTP {reply.status}; evidence unavailable.")
        if reply.getheader("Content-Encoding", "identity") not in ("identity", ""):
            return Response(problem="Unsupported response encoding.")
        body = bytearray()
        while True:
            if time.monotonic() - started > 15:
                return Response(problem="Response deadline exceeded.")
            block = reply.read1(min(65536, LIMIT + 1 - len(body)))
            if not block:
                break
            body.extend(block)
            if len(body) > LIMIT:
                return Response(problem="Response exceeds size limit.")
        text = body.decode("utf-8")
        load_json(text, LIMITS)
        data = json.loads(text, object_pairs_hook=_unique)
        # Never follow a server-supplied URL with credentials. Partial rule pages
        # cannot establish absence of an alternative enforcement mechanism.
        more = bool(reply.getheader("Link"))
        return Response(data=data, paginated=more)
    except (OSError, http.client.HTTPException, UnicodeError, ValueError, PawlError):
        return Response(problem="GitHub response could not be safely verified.")
    finally:
        connection.close()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def inspect_github(
    repository: str | None,
    branch: str | None,
    expected_check: str | None,
    expected_app_id: int | None,
) -> list[Observation]:
    observations: list[Observation] = []
    unknown = {
        name: Observation(
            "ci." + name,
            "unknown",
            "Requires additional authenticated or operator evidence.",
            "not verified",
        )
        for name in CONTROLS
    }
    if (
        not repository
        or len(repository) > 256
        or not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository)
        or repository.split("/")[-1] in (".", "..")
        or not branch
        or len(branch) > 255
        or branch.startswith("-")
        or any(ord(c) < 33 or ord(c) > 126 for c in branch)
        or any(part in branch for part in ("..", "@{", "*", "?", "[", "\\"))
    ):
        observations.append(
            Observation(
                "github.target",
                "unknown",
                "Explicit valid --repository OWNER/REPO and --branch are required.",
                "arguments",
            )
        )
        return observations + list(unknown.values())
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        observations.append(
            Observation(
                "github.authentication",
                "unknown",
                "No GH_TOKEN or GITHUB_TOKEN supplied to the trusted diagnostic process.",
                "launcher environment",
            )
        )
        return observations + list(unknown.values())
    prefix = "/repos/" + repository
    branch_path = prefix + "/branches/" + quote(branch, safe="")
    branch_result = fetch(branch_path, token)
    branch_data = _mapping(branch_result.data)
    sha = _mapping(branch_data.get("commit")).get("sha")
    if (
        branch_result.problem
        or branch_result.paginated
        or branch_data.get("name") != branch
        or not isinstance(sha, str)
        or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha)
    ):
        observations.append(
            Observation(
                "github.branch",
                "unknown",
                branch_result.problem or "Branch response is malformed or mismatched.",
                "https://" + HOST + branch_path,
            )
        )
        return observations + list(unknown.values())
    observations.append(
        Observation(
            "github.branch",
            "pass",
            f"Observed {repository} branch {branch} at {sha}.",
            "https://" + HOST + branch_path,
        )
    )
    protection_path = branch_path + "/protection"
    rules_path = prefix + "/rules/branches/" + quote(branch, safe="") + "?per_page=100"
    protection, rules = fetch(protection_path, token), fetch(rules_path, token)
    classic = _mapping(protection.data)
    protection_ok = (
        not protection.problem
        and not protection.paginated
        and isinstance(protection.data, dict)
        and type(_mapping(classic.get("enforce_admins")).get("enabled")) is bool
        and all(
            key in classic and (classic[key] is None or isinstance(classic[key], dict))
            for key in ("required_pull_request_reviews", "required_status_checks")
        )
    )
    rules_ok = (
        not rules.problem
        and not rules.paginated
        and isinstance(rules.data, list)
        and all(isinstance(rule, dict) and isinstance(rule.get("type"), str) for rule in rules.data)
    )
    observations += [
        Observation(
            "github.branch_protection",
            "pass" if protection_ok else "unknown",
            "Classic protection settings observed; this alone does not establish CI readiness."
            if protection_ok
            else protection.problem or "Protection response is malformed or partial.",
            "https://" + HOST + protection_path,
        ),
        Observation(
            "github.branch_rules",
            "pass" if rules_ok else "unknown",
            f"{len(rules.data)} active rule records observed; bypass semantics not certified."
            if rules_ok
            else rules.problem or "Rules response is malformed or partial.",
            "https://" + HOST + rules_path,
        ),
    ]
    if not protection_ok:
        return observations + list(unknown.values())
    reviews = _mapping(classic.get("required_pull_request_reviews"))
    admins = _mapping(classic.get("enforce_admins")).get("enabled") is True
    bypass = _mapping(reviews.get("bypass_pull_request_allowances"))
    no_bypass = all(key in bypass and bypass[key] == [] for key in ("users", "teams", "apps"))
    count = reviews.get("required_approving_review_count")
    strong_reviews = type(count) is int and count >= 1 and admins and no_bypass
    no_alternative = rules_ok and rules.data == []
    source = "https://" + HOST + protection_path
    if strong_reviews and reviews.get("require_last_push_approval") is True:
        unknown["last_push_review"] = Observation(
            "ci.last_push_review",
            "pass",
            "Classic policy requires last-push approval, applies to admins, "
            "and has no listed review bypass.",
            source,
        )
    elif no_alternative and reviews.get("require_last_push_approval") is False:
        unknown["last_push_review"] = Observation(
            "ci.last_push_review",
            "fail",
            "Last-push review is disabled and no active branch rules supply it.",
            source,
        )
    checks = _mapping(classic.get("required_status_checks"))
    bindings = checks.get("checks")
    expected = (
        isinstance(expected_check, str)
        and 0 < len(expected_check) <= 256
        and type(expected_app_id) is int
        and expected_app_id > 0
    )
    bound = (
        expected
        and isinstance(bindings, list)
        and any(
            isinstance(item, dict)
            and item.get("context") == expected_check
            and type(item.get("app_id")) is int
            and item["app_id"] == expected_app_id
            for item in bindings
        )
    )
    if checks.get("strict") is True and bound and admins and no_bypass:
        unknown["current_base_checks"] = Observation(
            "ci.current_base_checks",
            "pass",
            "Strict current-base checks bind the explicitly requested context and GitHub App.",
            source,
        )
    elif no_alternative and checks.get("strict") is False:
        unknown["current_base_checks"] = Observation(
            "ci.current_base_checks",
            "fail",
            "Strict current-base status checks are disabled and no active rules supply them.",
            source,
        )
    # Settings cannot establish separate human/agent credentials, valid CODEOWNERS
    # coverage, immutable workflow implementation, or publisher isolation.
    return observations + list(unknown.values())
