# envman — .env file manager

A small command-line tool for reading and editing `.env` files without
destroying them. Most dotenv tools rewrite the whole file when you change
one value; envman keeps your comments, blank lines and ordering, and only
rewrites the line that changed.

## What it does

- `get`, `set`, `unset` and `list` keys in a `.env` file
- `check` a `.env` against a `.env.example` template — missing, empty and
  extra keys, so a deploy never fails on a forgotten variable
- `diff` two env files (dev vs production, before vs after)
- `export` values as shell `export` lines or JSON
- Redact secret values (`--redact`) so `API_KEY` never lands in a pasted
  terminal transcript

## Design decisions

1. **The parser preserves file shape.** Comments and blank lines are kept
   as entries, so a `set` is a one-line edit, not a full rewrite. This is
   the whole point of the tool: config files are read by humans too.
2. **Saves are atomic.** Writes go to a temporary file in the same
   directory and are moved into place with `os.replace`, so a crash or a
   killed process can never leave a half-written `.env`.
3. **Parsing is strict about real-world syntax.** Single quotes are
   literal, double quotes unescape and expand `$VAR`, inline comments only
   count after whitespace, and multi-line double-quoted values work. A
   line that is none of these is a parse error, not silently skipped.
4. **No dependencies.** The standard library only, so it runs anywhere
   Python 3.9+ runs, including inside a container with no network.

## Install

```bash
pip install .
```

## Usage

```bash
envman list .env
envman get .env DATABASE_URL
envman set .env DEBUG true
envman set .env GREETING "hello world" --quote '"'
envman unset .env OLD_KEY
envman check .env .env.example
envman diff .env .env.production
envman export .env --format json
envman list .env --redact
```

`check` exits non-zero when a required key is missing or empty, so it
fits in a CI step or a deploy script:

```bash
envman check .env .env.example || echo "env incomplete, aborting deploy"
```

## Parsing rules

- `KEY=value`, `export KEY=value`, `KEY=` (empty value)
- `#` full-line comments; inline `# comment` only after whitespace
- `'single quotes'` — literal, no expansion
- `"double quotes"` — `\n`, `\t`, `\"`, `\\` unescaped, `$VAR` and
  `${VAR}` expanded from earlier keys, then the process environment
- Multi-line double-quoted values
- Later duplicates win, matching most dotenv loaders

## Tests

```bash
pip install pytest
python -m pytest
```

## Tech stack

- Python 3.9+ standard library only
- pytest for the test suite
