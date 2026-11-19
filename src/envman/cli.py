"""Command-line interface for envman.

Usage examples::

    envman list .env
    envman get .env DATABASE_URL
    envman set .env DEBUG true
    envman set .env API_KEY secret --redact
    envman unset .env OLD_KEY
    envman check .env .env.example
    envman diff .env .env.production
    envman export .env --format json
"""

from __future__ import annotations

import argparse
import json
import sys

from .checker import check_against_template, diff_envs
from .manager import EnvFile
from .parser import ParseError

__all__ = ["main"]


def _load(path: str) -> EnvFile:
    try:
        return EnvFile(path)
    except ParseError as exc:
        print(f"envman: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _redact(key: str, value: str) -> str:
    if any(hint in key.upper() for hint in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
        if len(value) <= 4:
            return "*" * len(value)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="envman", description="Manage .env files without losing comments."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List all keys and values.")
    p_list.add_argument("file")
    p_list.add_argument("--redact", action="store_true", help="Mask secret values.")

    p_get = sub.add_parser("get", help="Print one value.")
    p_get.add_argument("file")
    p_get.add_argument("key")
    p_get.add_argument("--redact", action="store_true", help="Mask secret values.")

    p_set = sub.add_parser("set", help="Set a key (creates it when missing).")
    p_set.add_argument("file")
    p_set.add_argument("key")
    p_set.add_argument("value")
    p_set.add_argument("--quote", choices=["", "'", '"'], default="",
                       help="Quote style for the stored value.")

    p_unset = sub.add_parser("unset", help="Remove a key.")
    p_unset.add_argument("file")
    p_unset.add_argument("key")

    p_check = sub.add_parser("check", help="Check against a template file.")
    p_check.add_argument("file")
    p_check.add_argument("template")

    p_diff = sub.add_parser("diff", help="Diff two env files.")
    p_diff.add_argument("old")
    p_diff.add_argument("new")

    p_export = sub.add_parser("export", help="Print values as shell or JSON.")
    p_export.add_argument("file")
    p_export.add_argument("--format", choices=["shell", "json"], default="shell")

    args = parser.parse_args(argv)

    if args.command == "list":
        env = _load(args.file)
        for key, value in env.to_dict().items():
            shown = _redact(key, value) if args.redact else value
            print(f"{key}={shown}")
        return 0

    if args.command == "get":
        env = _load(args.file)
        value = env.get(args.key)
        if value is None:
            print(f"envman: {args.key} not found", file=sys.stderr)
            return 1
        print(_redact(args.key, value) if args.redact else value)
        return 0

    if args.command == "set":
        env = _load(args.file)
        env.set(args.key, args.value, quote=args.quote)
        env.save()
        print(f"set {args.key}")
        return 0

    if args.command == "unset":
        env = _load(args.file)
        if not env.unset(args.key):
            print(f"envman: {args.key} not found", file=sys.stderr)
            return 1
        env.save()
        print(f"removed {args.key}")
        return 0

    if args.command == "check":
        env, template = _load(args.file), _load(args.template)
        result = check_against_template(env, template)
        for key in result.missing:
            print(f"missing: {key}")
        for key in result.empty:
            print(f"empty: {key}")
        for key in result.extra:
            print(f"extra: {key}")
        if result.ok:
            print("ok: all required keys present")
            return 0
        return 1

    if args.command == "diff":
        old, new = _load(args.old), _load(args.new)
        result = diff_envs(old, new)
        for key, value in result.added.items():
            print(f"+ {key}={value}")
        for key, value in result.removed.items():
            print(f"- {key}={value}")
        for key, (before, after) in result.changed.items():
            print(f"~ {key}: {before} -> {after}")
        if result.empty:
            print("no differences")
        return 0

    if args.command == "export":
        env = _load(args.file)
        data = env.to_dict()
        if args.format == "json":
            print(json.dumps(data, indent=2, sort_keys=True))
        else:
            for key, value in data.items():
                print(f"export {key}={_shell_quote(value)}")
        return 0

    return 0


def _shell_quote(value: str) -> str:
    if value and all(c.isalnum() or c in "_-./:@%+" for c in value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
