# Pixflix

PIX-powered interactive terminal tooling for arcades.

## Goal

Build a terminal flow where a customer pays (for example R$1 via PIX) and then earns one interaction, starting with selecting a song to play on the arcade sound system.

## Project status

Initial repository scaffold:

- Python project with packaging metadata
- Source + tests structure
- Linting with Ruff
- CI pipeline (GitHub Actions) for lint + tests

## Tech baseline

- Python `3.12`
- Build backend: `hatchling`
- Test runner: `pytest`
- Linter: `ruff`

## Quickstart

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
ruff check .
```

## Suggested next milestones

1. Define PIX payment provider strategy and webhook model.
2. Create a local "credit" ledger (paid interactions).
3. Build terminal UI flow: pending payment -> paid -> choose song -> queue song.
4. Integrate with the local audio playback service.
5. Add audit logs and anti-abuse limits.

