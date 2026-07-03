# EE Toolkit — Project Instructions

Unified Python CLI for electronics/embedded workflows.

## Project Layout

- `src/ee_toolkit/` — Python package source
- `src/ee_toolkit/commands/` — CLI subcommands
- `src/ee_toolkit/core/` — shared libraries
- `src/ee_toolkit/capture/` — ATK-Logic capture modules
- `src/ee_toolkit/data/` — package data (templates, etc.)
- `docs/` — design and planning documents
- `.venv/` — local Python virtual environment (not committed)

## Development Constraints

- Python >= 3.10
- LF line endings only
- UTF-8 encoding
- Use `uv` or `python -m venv` to create `.venv` before installing dependencies
- Prefer `bun`/`npm` only if frontend assets are added (currently none)
- Do not modify `/node_modules`

## CLI Entry

After installation, the global command is `ee`:

```bash
ee serial listen --port COM7
ee capture start --ch 2,3
ee keil init .
```

## Testing

- Use `pytest`
- Hardware-dependent commands (`serial listen`, `capture start`) must be mockable or skipped in CI
- Every command module should have a corresponding test under `tests/`

## Commits

- One logical unit per commit
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- End commit messages with:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

## Skill Integration

`C:\Users\yg\.claude\skills\ee-toolkit` is a junction pointing to this directory.
`SKILL.md` at the project root provides the thin agent entry point for `/ee ...`.
