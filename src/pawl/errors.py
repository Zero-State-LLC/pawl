"""Exception types. Every error maps to a fail-closed exit code."""

from __future__ import annotations


class PawlError(Exception):
    """A configuration, parsing, or runner error. Pawl exits 2 and never passes."""


class ConfigError(PawlError):
    """The configuration or baseline file is missing or invalid."""


class ParseError(PawlError):
    """Runner output could not be read with confidence. Pawl fails closed."""


class PreflightError(PawlError):
    """The environment is not the one the baseline was measured in."""
