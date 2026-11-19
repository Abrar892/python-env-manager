"""In-memory model of a .env file with safe, atomic writes.

Edits keep the file's comments, blank lines and ordering: a ``set`` only
rewrites the line that changed, and a new key is appended at the end.
Saves go through a temporary file plus ``os.replace`` so a crash mid-write
never leaves a half-written .env behind.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .parser import Entry, pairs, parse_env_text

__all__ = ["EnvFile"]


class EnvFile:
    def __init__(self, path: str | Path, text: str | None = None):
        self.path = Path(path)
        if text is None:
            text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        self.entries: list[Entry] = parse_env_text(text)

    def to_dict(self) -> dict[str, str]:
        return pairs(self.entries)

    def get(self, key: str, default: str | None = None) -> str | None:
        for entry in self.entries:
            if entry.kind == "pair" and entry.key == key:
                return entry.value
        return default

    def set(self, key: str, value: str, *, quote: str = "") -> None:
        """Set a key, updating its existing line in place when present."""
        for entry in self.entries:
            if entry.kind == "pair" and entry.key == key:
                entry.value = value
                entry.quoted = quote or entry.quoted
                return
        self.entries.append(Entry(kind="pair", key=key, value=value, quoted=quote))

    def unset(self, key: str) -> bool:
        """Remove a key. Returns True when a key was actually removed."""
        before = len(self.entries)
        self.entries = [
            e for e in self.entries if not (e.kind == "pair" and e.key == key)
        ]
        return len(self.entries) != before

    def keys(self) -> list[str]:
        return [e.key for e in self.entries if e.kind == "pair"]

    def render(self) -> str:
        text = "\n".join(e.render() for e in self.entries)
        return text + "\n" if text else ""

    def save(self) -> None:
        """Write the file atomically, preserving its permissions when it exists."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(self.render())
            if self.path.exists():
                os.chmod(tmp, self.path.stat().st_mode)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
