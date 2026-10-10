"""Where the gate definition comes from in this run.

One place answers "which config and baseline does this run trust?" for
``pawl check``, ``pawl guard``, and the stop hook, so they cannot disagree.

With a trusted ref (CI), the config and baseline come from the merge base of
that ref, read from git at the same path ``--root`` has in the working tree
(``pkg/pawl.toml`` when the root is ``pkg/``). The head baseline can only
tighten it: Pawl uses the stricter of the two. A human approval switches to the
head config and baseline.

If the base has no config, Pawl refuses unless this is an approved change or
``--bootstrap`` is passed. A silent fallback to the head config would let a
change pick its own gate whenever the lookup misses (review finding F2: a
config in a subdirectory was looked up at the top level, missed, and the head
config was used).
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawl.baseline import Baseline, check_quarantine, load_baseline, parse_baseline, stricter
from pawl.config import CONFIG_NAME, Config, GuardConfig, load_config, parse_config
from pawl.errors import ConfigError
from pawl.gitutil import git, merge_base, prefix, show


@dataclass
class Approval:
    """A human approval of a gate change, bound to one commit."""

    source: str  # "flag" (--approved) or "label"
    sha: str
    label: str = ""
    actor: str = ""
    actor_type: str = ""
    event: str = ""
    action: str = ""
    run_id: str = ""
    pr: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {"source": self.source, "label": self.label, "sha": self.sha}

    def provenance(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "label": self.label,
            "sha": self.sha,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "event": self.event,
            "action": self.action,
            "run_id": self.run_id,
            "pr": self.pr,
        }

    def describe(self) -> str:
        if self.source == "label":
            return (
                f"approved by label '{self.label}' applied by {self.actor} "
                f"({self.event}/{self.action}, run {self.run_id}) at commit {self.sha[:12]}"
            )
        return f"approved by --approved at commit {self.sha[:12]}"


def _checked_out(root: Path) -> set[str]:
    """Commits this run is checking: HEAD, and for a pull request merge commit, the PR head."""
    shas = git(root, "rev-list", "--parents", "-n", "1", "HEAD", check=False).split()
    if not shas:
        return set()
    return {shas[0], shas[2]} if len(shas) == 3 else {shas[0]}


def label_approval(
    label: str,
    root: Path,
    approvers: tuple[str, ...] = (),
    refuse_pr_author: bool = False,
) -> tuple[Approval | None, str | None]:
    """Read the approval label from the GitHub event. Returns (approval, note).

    The label counts only in the run its own application triggered, and only for
    the commit it was applied at: the event must be ``labeled`` with this label,
    and the event's ``pull_request.head.sha`` must be the commit checked out.
    A label left on the PR does not approve later pushes (``synchronize``) or
    runs triggered by other labels; a human re-applies it to approve again.
    """
    event = os.environ.get("GITHUB_EVENT_PATH")
    if not event or not Path(event).is_file():
        return None, None
    try:
        data = json.loads(Path(event).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    pr = data.get("pull_request") or {}
    action = str(data.get("action", ""))
    applied = (data.get("label") or {}).get("name")
    sender = data.get("sender") or {}
    actor = str(sender.get("login") or "")
    actor_type = str(sender.get("type") or "")
    if action == "unlabeled" and applied == label:
        return None, (
            f"label '{label}' was removed by {actor or 'unknown'}: approval revoked; "
            "this run is not approved"
        )
    names = {i.get("name") for i in pr.get("labels") or [] if isinstance(i, dict)}
    if label not in names:
        return None, None
    if action != "labeled" or applied != label:
        return None, (
            f"label '{label}' is on the pull request but did not trigger this run "
            f"(event '{action}'); it approves only the commit it was applied at. "
            "Re-apply the label to approve the current commit."
        )
    head_sha = str((pr.get("head") or {}).get("sha", ""))
    checked = _checked_out(root)
    if not head_sha or head_sha not in checked:
        return None, (
            f"label '{label}' was applied at {head_sha[:12] or 'an unknown commit'}, "
            f"but this run checks {', '.join(sorted(x[:12] for x in checked)) or 'nothing'}. "
            "Re-apply the label to approve the current commit."
        )
    if not actor:
        return None, (
            f"label '{label}' has no recorded sender; an approval is never inferred "
            "from the label name alone"
        )
    if actor_type == "Bot" or actor.endswith("[bot]"):
        return None, f"label '{label}' was applied by bot {actor}; only a human approves"
    if approvers and actor not in approvers:
        return None, f"label '{label}' was applied by {actor}, who is not in guard.approvers"
    author = str(((pr.get("user") or {}).get("login")) or "")
    if refuse_pr_author and author and actor == author:
        return None, (
            f"label '{label}' was applied by the pull request author {actor}; "
            "another human must approve"
        )
    return (
        Approval(
            "label",
            head_sha,
            label,
            actor=actor,
            actor_type=actor_type,
            event=os.environ.get("GITHUB_EVENT_NAME", ""),
            action=action,
            run_id=os.environ.get("GITHUB_RUN_ID", ""),
            pr=pr.get("number") if isinstance(pr.get("number"), int) else None,
        ),
        None,
    )


@dataclass
class TrustedGate:
    """The config and baseline this run trusts, and why."""

    config: Config
    baseline: Baseline | None
    source: str
    notes: list[str] = field(default_factory=list)
    approval: Approval | None = None


DEFAULT_APPROVAL_LABEL = GuardConfig().approval_label


def resolve(
    root: Path,
    ref: str | None,
    *,
    approved: bool = False,
    bootstrap: bool = False,
    need_baseline: bool = True,
    today: dt.date | None = None,
) -> TrustedGate:
    """Resolve the trusted gate definition for ``root``.

    ``ref`` is the trusted base ref (``--trusted-ref`` or ``--base``); without it
    the working tree is trusted (local runs). ``approved`` is the ``--approved``
    flag; the approval label is read here. Raises ConfigError (exit 2) when the
    gate definition cannot be established.
    """
    today = today or dt.date.today()
    gate = _resolve(
        root,
        ref,
        approved=approved,
        bootstrap=bootstrap,
        need_baseline=need_baseline,
        today=today,
    )
    if gate.baseline is not None:
        # The trusted config's limit applies to every baseline this run reads.
        check_quarantine(gate.baseline, gate.config.quarantine_max_days, today, gate.source)
    return gate


def _resolve(
    root: Path,
    ref: str | None,
    *,
    approved: bool,
    bootstrap: bool,
    need_baseline: bool,
    today: dt.date,
) -> TrustedGate:
    head = load_config(root)
    head_bl = load_baseline(head.baseline_path) if head.baseline_path.is_file() else None

    def head_gate(notes: list[str], approval: Approval | None = None) -> TrustedGate:
        if need_baseline and head_bl is None:
            raise ConfigError(f"no baseline at {head.baseline_path}; run 'pawl init'")
        return TrustedGate(head, head_bl, head.source, notes, approval)

    if not ref:
        return head_gate([])
    mb = merge_base(root, ref)
    where = prefix(root) + CONFIG_NAME
    base_text = show(root, mb, where)
    base_cfg = (
        parse_config(base_text, root, source=f"{ref}:{where}") if base_text is not None else None
    )
    # The label name comes from the base config, so a branch cannot rename the
    # label to one it controls. With no base config (a branch adding Pawl), the
    # head config is untrusted too, so only the default label counts.
    label = base_cfg.guard.approval_label if base_cfg is not None else DEFAULT_APPROVAL_LABEL
    approvers = base_cfg.guard.approvers if base_cfg is not None else ()
    refuse_author = base_cfg.guard.refuse_pr_author if base_cfg is not None else False
    label_note: list[str] = []
    if approved:
        approval: Approval | None = Approval("flag", git(root, "rev-parse", "HEAD").strip())
    else:
        approval, why = label_approval(label, root, approvers, refuse_pr_author=refuse_author)
        label_note = [why] if why else []
    if approval is not None and not need_baseline and base_cfg is not None:
        # The guard keeps the base rules when approved: its findings are the
        # record of what the human approved, so the branch must not shape them.
        note = f"{approval.describe()}: gate definition from {ref}; findings are recorded"
        return TrustedGate(base_cfg, None, base_cfg.source, [note], approval)
    if approval is not None:
        return head_gate([f"{approval.describe()}: using the head config and baseline"], approval)
    if base_cfg is None:
        if not bootstrap:
            raise ConfigError(
                f"{ref} has no {where} at the merge base {mb[:12]}, so there is no trusted "
                "gate definition. If this change adds Pawl, a human approves it with the "
                f"'{label}' label (or --approved), or pass --bootstrap. Otherwise check the "
                "ref and --root."
            )
        return head_gate([*label_note, f"bootstrap: no {where} on {ref}; using the head config"])
    if not need_baseline:
        notes = [*label_note, f"gate definition from {ref}"]
        return TrustedGate(base_cfg, None, base_cfg.source, notes)
    bl_where = prefix(root) + base_cfg.baseline
    bl_text = show(root, mb, bl_where)
    if bl_text is None:
        raise ConfigError(f"{ref} has {where} but no {bl_where}")
    base_bl = parse_baseline(bl_text, f"{ref}:{bl_where}")
    if head_bl is not None:
        check_quarantine(head_bl, base_cfg.quarantine_max_days, today, "head baseline")
    if head_bl is None:
        return TrustedGate(
            base_cfg,
            base_bl,
            base_cfg.source,
            [*label_note, f"gate definition from {ref}; head baseline missing"],
        )
    return TrustedGate(
        base_cfg,
        stricter(base_bl, head_bl),
        base_cfg.source,
        [*label_note, f"gate definition from {ref}; stricter of base and head baselines"],
    )
