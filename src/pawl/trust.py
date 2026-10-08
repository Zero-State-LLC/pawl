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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawl.baseline import Baseline, load_baseline, parse_baseline, stricter
from pawl.config import CONFIG_NAME, Config, GuardConfig, load_config, parse_config
from pawl.errors import ConfigError
from pawl.gitutil import merge_base, prefix, show


@dataclass
class Approval:
    """A human approval of a gate change."""

    source: str  # "flag" (--approved) or "label"
    label: str = ""

    def to_json(self) -> dict[str, Any]:
        return {"source": self.source, "label": self.label}

    def describe(self) -> str:
        if self.source == "label":
            return f"approved by label '{self.label}'"
        return "approved by --approved"


@dataclass
class TrustedGate:
    """The config and baseline this run trusts, and why."""

    config: Config
    baseline: Baseline | None
    source: str
    notes: list[str] = field(default_factory=list)
    approval: Approval | None = None


def _label_approval(label: str) -> Approval | None:
    from pawl.guard import approved_by_label

    return Approval("label", label) if approved_by_label(label) else None


DEFAULT_APPROVAL_LABEL = GuardConfig().approval_label


def resolve(
    root: Path,
    ref: str | None,
    *,
    approved: bool = False,
    bootstrap: bool = False,
    need_baseline: bool = True,
) -> TrustedGate:
    """Resolve the trusted gate definition for ``root``.

    ``ref`` is the trusted base ref (``--trusted-ref`` or ``--base``); without it
    the working tree is trusted (local runs). ``approved`` is the ``--approved``
    flag; the approval label is read here. Raises ConfigError (exit 2) when the
    gate definition cannot be established.
    """
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
    approval = Approval("flag") if approved else _label_approval(label)
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
        return head_gate([f"bootstrap: no {where} on {ref}; using the head config"])
    if not need_baseline:
        return TrustedGate(base_cfg, None, base_cfg.source, [f"gate definition from {ref}"])
    bl_where = prefix(root) + base_cfg.baseline
    bl_text = show(root, mb, bl_where)
    if bl_text is None:
        raise ConfigError(f"{ref} has {where} but no {bl_where}")
    base_bl = parse_baseline(bl_text, f"{ref}:{bl_where}")
    if head_bl is None:
        return TrustedGate(
            base_cfg,
            base_bl,
            base_cfg.source,
            [f"gate definition from {ref}; head baseline missing"],
        )
    return TrustedGate(
        base_cfg,
        stricter(base_bl, head_bl),
        base_cfg.source,
        [f"gate definition from {ref}; stricter of base and head baselines"],
    )
