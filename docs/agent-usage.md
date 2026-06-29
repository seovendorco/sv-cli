# Agent Usage

Agents and automated workflows should use strict, non-interactive, machine-readable commands.

```bash
sv seogpt generate \
  --type 15 \
  --keyword "white label seo" \
  --strict \
  --no-fuzzy \
  --non-interactive \
  --format json
```

Raw mode is the most stable interface for agents that already know the API payload:

```bash
sv call seogpt \
  --json '{"action":"generate","kw":"white label seo","contenttype":15}' \
  --format json \
  --non-interactive
```

Recommendations:

- Use enum IDs or exact slugs.
- Use `--format json`.
- Use `--non-interactive` in CI, cron, and agents.
- Set `SV_API_KEY` in the environment.
- Refresh definitions during setup with `sv definitions refresh`.
