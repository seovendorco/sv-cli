# Contributing

Thanks for contributing to SV CLI.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Guidelines

- Keep API definitions as the source of truth.
- Add local adapters only for friendly command names, aliases, presets, and output polish.
- Do not hardcode API keys or real customer data in examples, fixtures, tests, or docs.
- Prefer strict, predictable behavior for agent-facing changes.
- Add tests for resolver, caching, auth/config, output formatting, and error handling changes.

## Pull requests

Before opening a PR:

```bash
ruff check .
pytest
python -m build
```

Describe user-facing behavior, backward compatibility, and any new commands.
