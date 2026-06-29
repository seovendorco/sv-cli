# SV CLI

SV CLI is an open-source command-line client for the SV AI API. It is designed as a definition-driven resolver layer: humans can use friendly commands, slugs, aliases, and presets, while scripts and AI agents can use strict enum IDs and raw JSON calls.

The CLI discovers available tools from the API root and fetches each tool's definitions endpoint at runtime. Definitions are cached locally for speed, refreshed automatically after 24 hours by default, and can be refreshed or cleared manually.

## Install

```bash
pip install sv-cli
```

For local development:

```bash
git clone https://github.com/seovendor/sv-cli.git
cd sv-cli
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
sv --help
```

## API key setup

An API key is required for API calls. Resolution order:

1. `--api-key` flag
2. `SV_API_KEY` environment variable
3. Stored profile config from `sv auth set`
4. Interactive prompt when allowed

`SV_API_KEY` is the current environment variable. `SEOVENDOR_API_KEY` is still accepted as a legacy fallback during migration.

Recommended setup:

```bash
sv auth set
sv auth status
```

CI setup:

```bash
export SV_API_KEY="your-key-here"
sv seogpt generate --type 15 --keyword "white label seo" --strict --format json --non-interactive
```

Avoid passing real keys with `--api-key` in shared shells because shell history may store the value. Debug output masks keys.

### Brand migration notes

The package, repository, executable, Python package, and local state directory now use the SV brand:

- PyPI package: `sv-cli`
- Executable: `sv`
- Python package: `sv_cli`
- Default local state directory: `~/.sv`
- Preferred environment variables: `SV_API_KEY` and `SV_HOME`

For migration safety, `SEOVENDOR_API_KEY`, `SEOVENDOR_HOME`, and an existing `~/.seovendor/config.json` are still accepted as fallbacks. New saves are written to `~/.sv`.

## Dynamic definitions cache

```bash
sv definitions refresh
sv definitions list
sv definitions show seogpt
sv definitions clear
```

Cache location:

```text
~/.sv/cache/definitions.json
```

The old `~/.seovendor/config.json` file is read as a migration fallback when `~/.sv/config.json` does not exist. New writes go to `~/.sv`.

Default behavior:

- Use local cache when present.
- Refresh automatically if the cache is older than 24 hours.
- Use stale cache with a warning if refresh fails.
- Error clearly if no cache exists and definitions cannot be fetched.

## Quick start

```bash
sv keywords research --keyword "white label seo"
sv seogpt generate --type meta-description --keyword "white label seo" --url https://example.com
sv geo-audit run --url https://example.com --keywords "seo agency,white label seo" --wait
sv image generate --keyword "white label seo" --type blog-header
sv top-competitors analyze --keyword "white label seo"
sv marketplace-services search --search "seo audit" --price 500 --category SEO
sv content-quality analyze --keyword "white label seo" --url https://example.com
```

Presets:

```bash
sv meta --url https://example.com --keyword "white label seo"
sv title --url https://example.com --keyword "white label seo"
sv keywords --keyword "white label seo"
sv audit --url https://example.com --keywords "white label seo" --wait
sv image --keyword "white label seo"
```

## Supported tools

| Friendly command | Aliases | API tool key |
| --- | --- | --- |
| `better-keywords` | `keywords` | `better-keywords` |
| `content-transformer` | `transform` | `content-transformer` |
| `core-analysis` | `core` | `core-analysis` |
| `geo-audit` | `geogpt-audit`, `audit` | `geogptaudit` |
| `insight-igniter` | `insights` | `insight-igniter` |
| `preliminary-audit` | `prelim-audit` | `preliminaryaudit` |
| `ranklens` | | `ranklens` |
| `seo-image` | `image` | `seo-image` |
| `seogpt` | `seo-gpt` | `seogpt` |
| `seogpt2` | `seo-gpt2` | `seogpt2` |
| `seogpt-compare` | `compare` | `seogptcompare` |
| `seo-mapping` | `mapping` | `seogptmapping` |
| `topical-authority` | `topical` | `topical-authority` |
| `top-competitors` | `competitors` | `top-competitors` |
| `marketplace-services` | `marketplace`, `services` | `marketplace-services` |
| `content-quality` | `quality`, `hcu-quality`, `eeat-quality` | `content-quality` |

The canonical API tool keys are discovered from the live API root; local aliases are only a human-friendly layer. For newly released tools, the CLI can also use adapter-provided endpoint hints until the API root advertises those tools. Root-discovered metadata still takes precedence.

## Enum resolution

For enum-heavy fields such as content type, language, engine, image type, theme, background, color, and size, the CLI resolves values in this order:

1. Numeric ID exact match
2. Exact slug match
3. Exact canonical API value
4. Exact alias match
5. Exact label match
6. Normalized exact match
7. Prefix match
8. Contains match
9. Fuzzy match with safe thresholds

Examples that may resolve to the same API enum when definitions contain those aliases:

```bash
--type 15
--type meta-description
--type "Meta Description"
--type "meta desc"
--type "seo description"
```

Agent-safe mode:

```bash
sv seogpt generate --type 15 --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
```

## Options discovery

```bash
sv options list
sv options seogpt
sv options seogpt contenttype --search meta
sv seogpt types --search meta
sv seogpt languages
sv image themes --search luxury
```

## Raw API calls

Raw calls use live definitions only to find the selected tool endpoint. The payload is otherwise passed through unchanged except that `k` is injected when no API-key field already exists.

```bash
sv call seogpt --json '{"action":"generate","kw":"white label seo","contenttype":15}' --format json
sv call seogpt --file payload.json --format json
cat payload.json | sv call seogpt --stdin --format json
```

## Async task handling

For tools that return task IDs:

```bash
sv geo-audit run --url https://example.com --keywords "seo agency" --wait
sv task status TASK_ID --tool geo-audit
sv task result TASK_ID --tool geo-audit
```

If a task is created through the CLI, its tool mapping is stored in `~/.sv/tasks.json`, so `--tool` is usually optional later.

## Output formats

```bash
--format pretty
--format json
--format table
--format csv
--format markdown
--format text
```

Examples:

```bash
sv keywords research --keyword "white label seo" --format csv --output keywords.csv
sv geo-audit run --url https://example.com --keywords "seo agency" --wait --format markdown --output audit.md
```

## Profiles

```bash
sv profile create agency-a
sv --profile agency-a auth set
sv profile use agency-a
sv profile list
sv profile delete agency-a
```

Profile config is stored in `~/.sv/config.json`, not in project folders.

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
python -m build
```

Live tests should be opt-in only:

```bash
SV_API_KEY=... RUN_LIVE_TESTS=1 pytest -m live
```

## Security

Never commit API keys, `.env`, or `~/.sv/config.json`. The repository `.gitignore` excludes common secret/config files. Report vulnerabilities using the process in `SECURITY.md`.
