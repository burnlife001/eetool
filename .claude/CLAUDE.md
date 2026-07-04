# eetool — Project Instructions

Unified Python CLI for electronics/embedded workflows.

## Project Layout

- `src/eetool/` — Python package source
- `src/eetool/commands/` — CLI subcommands
- `src/eetool/core/` — shared libraries
- `src/eetool/capture/` — ATK-Logic capture modules
- `src/eetool/data/` — package data (templates, etc.)
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

After installation, the global command is `eetool`:

```bash
eetool serial listen --port COM7
eetool capture start --ch 2,3
eetool keil init .
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

`C:\Users\yg\.claude\skills\eetool` is a junction pointing to this directory.
`SKILL.md` at the project root provides the thin agent entry point for `/eetool ...`.
