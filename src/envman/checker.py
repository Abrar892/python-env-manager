"""Checks and diffs between .env files.

``check`` answers the question every deploy asks: does this .env have
everything the ``.env.example`` template requires, and nothing stale?
``diff`` compares two env files key by key.
"""

from __future__ import annotations

from dataclasses import dataclass

from .manager import EnvFile

__all__ = ["CheckResult", "DiffResult", "check_against_template", "diff_envs"]


@dataclass
class CheckResult:
    missing: list[str]
    empty: list[str]
    extra: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.empty


@dataclass
class DiffResult:
    added: dict[str, str]
    removed: dict[str, str]
    changed: dict[str, tuple[str, str]]

    @property
    def empty(self) -> bool:
        return not self.added and not self.removed and not self.changed


def check_against_template(env: EnvFile, template: EnvFile) -> CheckResult:
    """Compare an env file against a template (usually .env.example).

    A template key with an empty value means "required, any value". A
    template key with a value means "required, and this is its default".
    """
    actual = env.to_dict()
    required = template.to_dict()
    missing = [k for k in required if k not in actual]
    empty = [k for k in required if k in actual and actual[k] == ""]
    extra = [k for k in actual if k not in required]
    return CheckResult(missing=missing, empty=empty, extra=extra)


def diff_envs(old: EnvFile, new: EnvFile) -> DiffResult:
    a, b = old.to_dict(), new.to_dict()
    added = {k: v for k, v in b.items() if k not in a}
    removed = {k: v for k, v in a.items() if k not in b}
    changed = {k: (a[k], b[k]) for k in a if k in b and a[k] != b[k]}
    return DiffResult(added=added, removed=removed, changed=changed)
