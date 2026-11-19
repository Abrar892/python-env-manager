"""Parser for .env files.

The parser keeps the file's shape: comments and blank lines survive a
round-trip, so editing a value never rewrites the whole file. It handles
the syntax real .env files use in the wild:

- ``KEY=value``, ``export KEY=value`` and keys with no value (``KEY=``)
- single quotes (literal) and double quotes (escapes + ``$VAR`` expansion)
- ``#`` full-line comments and inline comments after unquoted values
- multi-line double-quoted values
- ``${VAR}`` / ``$VAR`` expansion from keys seen earlier in the file,
  falling back to the process environment
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

__all__ = ["Entry", "ParseError", "parse_env_text"]

_KEY_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=(.*)$")
_VAR_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_.]*)\}|([A-Za-z_][A-Za-z0-9_.]*))")


class ParseError(ValueError):
    """Raised when a line cannot be parsed as a .env entry."""


@dataclass
class Entry:
    """One line of a .env file, kept in its original form."""

    kind: str  # "pair", "comment", or "blank"
    key: str = ""
    value: str = ""
    raw: str = ""
    quoted: str = ""  # "", "'", or '"'
    exported: bool = False

    def render(self) -> str:
        if self.kind != "pair":
            return self.raw
        prefix = "export " if self.exported else ""
        if self.quoted:
            body = self.quoted + _escape(self.value, self.quoted) + self.quoted
        else:
            body = self.value
        return f"{prefix}{self.key}={body}"


def _escape(value: str, quote: str) -> str:
    if quote == '"':
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
    return value.replace("'", "'\\''")


def _expand(value: str, seen: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        if name in seen:
            return seen[name]
        return os.environ.get(name, "")

    return _VAR_RE.sub(repl, value)


def _strip_inline_comment(text: str) -> str:
    """Remove a trailing ``# comment`` from an unquoted value.

    A ``#`` only starts a comment when it is preceded by whitespace,
    which is how ``KEY=value#not-a-comment`` keeps its ``#``.
    """
    in_single = in_double = False
    for i, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or text[i - 1] in " \t":
                return text[:i].rstrip()
    return text.rstrip()


def parse_env_text(text: str) -> list[Entry]:
    """Parse .env text into entries, preserving comments and order."""
    entries: list[Entry] = []
    seen: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            entries.append(Entry(kind="blank", raw=line))
            i += 1
            continue
        if stripped.startswith("#"):
            entries.append(Entry(kind="comment", raw=line))
            i += 1
            continue

        match = _KEY_RE.match(stripped)
        if not match:
            raise ParseError(f"Cannot parse line {i + 1}: {line!r}")
        key, raw_value = match.group(1), match.group(2)
        exported = stripped.startswith("export ")

        # Multi-line double-quoted value: keep consuming lines until the
        # closing quote shows up. The inner loop already advances past the
        # closing line, so the shared increment at the end is skipped.
        multiline = False
        if raw_value.lstrip().startswith('"') and not _has_closing_quote(
            raw_value.lstrip()
        ):
            multiline = True
            parts = [raw_value.lstrip()]
            i += 1
            while i < len(lines):
                parts.append(lines[i])
                i += 1
                if _has_closing_quote("\n".join(parts)):
                    break
            else:
                raise ParseError(f"Unterminated quoted value for {key!r}")
            raw_value = "\n".join(parts)

        value, quoted = _parse_value(raw_value, seen)
        seen[key] = value
        entries.append(
            Entry(
                kind="pair",
                key=key,
                value=value,
                raw=line,
                quoted=quoted,
                exported=exported,
            )
        )
        if not multiline:
            i += 1
    return entries


def _has_closing_quote(text: str) -> bool:
    """True when a double-quoted value in *text* is closed.

    Escaped quotes (``\\"``) do not count as the closing quote.
    """
    in_quote = False
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
        elif ch == "\\" and in_quote:
            escaped = True
        elif ch == '"':
            in_quote = not in_quote
    return not in_quote


def _parse_value(raw: str, seen: dict[str, str]) -> tuple[str, str]:
    raw = raw.strip()
    if raw.startswith('"'):
        end = _closing_quote_index(raw)
        if end == -1:
            raise ParseError(f"Unterminated quoted value: {raw!r}")
        return _expand(_unescape_double_quoted(raw[1:end]), seen), '"'
    if raw.startswith("'"):
        end = raw.find("'", 1)
        if end == -1:
            raise ParseError(f"Unterminated quoted value: {raw!r}")
        return raw[1:end], "'"
    return _expand(_strip_inline_comment(raw), seen), ""


def _unescape_double_quoted(inner: str) -> str:
    """Unescape a double-quoted value in one pass.

    Chained ``str.replace`` calls would misread ``\\n`` (an escaped
    backslash followed by ``n``) as a newline, so the scan consumes one
    escape sequence at a time. Unknown escapes keep their backslash.
    """
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _closing_quote_index(text: str) -> int:
    escaped = False
    for i in range(1, len(text)):
        ch = text[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return i
    return -1


def pairs(entries: list[Entry]) -> dict[str, str]:
    """Fold entries into a dict; later duplicates win, like most loaders."""
    result: dict[str, str] = {}
    for entry in entries:
        if entry.kind == "pair":
            result[entry.key] = entry.value
    return result
