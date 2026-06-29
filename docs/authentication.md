# Authentication

API calls require a SV API key.

Resolution order:

1. `--api-key`
2. `SV_API_KEY`
3. Stored profile config
4. Interactive prompt when allowed

`SEOVENDOR_API_KEY` is still accepted as a legacy fallback. New automation should use `SV_API_KEY`.

Recommended local setup:

```bash
sv auth set
sv auth status
```

Recommended CI setup:

```bash
export SV_API_KEY="..."
sv call seogpt --json '{"action":"generate","kw":"white label seo","contenttype":15}' --format json --non-interactive
```

Do not commit keys or paste real keys into issue trackers.


## Legacy migration

`SV_API_KEY` and `SV_HOME` are preferred. `SEOVENDOR_API_KEY`, `SEOVENDOR_HOME`, and an existing `~/.seovendor/config.json` remain supported as fallbacks while users migrate. New config and cache writes use `~/.sv`.
