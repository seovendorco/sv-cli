```
███████╗██╗   ██╗     ██████╗██╗     ██╗
██╔════╝██║   ██║    ██╔════╝██║     ██║
███████╗██║   ██║    ██║     ██║     ██║
╚════██║╚██╗ ██╔╝    ██║     ██║     ██║
███████║ ╚████╔╝     ╚██████╗███████╗██║
╚══════╝  ╚═══╝       ╚═════╝╚══════╝╚═╝

Agentic SEO & GEO from the command line
```
# SV CLI

SV CLI is an open-source command-line client for agentic SEO and GEO workflows using the SV API (SEO VENDOR API). It is designed as a definition-driven resolver layer: humans can use friendly commands, slugs, aliases, and presets, while scripts and AI agents can use strict enum IDs and raw JSON calls.

The CLI discovers available tools from the API root and fetches each tool's definitions endpoint at runtime. Definitions are cached locally for speed, refreshed automatically after 24 hours by default, and can be refreshed or cleared manually.

## Install

```bash
pip install sv-cli
```

For local development:

```bash
git clone https://github.com/seovendorco/sv-cli.git
cd sv-cli
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
sv --help
```

## MCP server (SV MCP)

SV MCP is the hosted [Model Context Protocol](https://modelcontextprotocol.io) server for the SV API, built on the same core library as this CLI. It gives Claude, Cursor, VS Code, Windsurf and other MCP clients the SV tools, with sign-in handled by OAuth.

- **Server URL:** `https://mcp.seovendor.co`
- **Transport:** Streamable HTTP
- **Auth:** OAuth 2.1 — your API key stays on the server
- **Repository:** https://github.com/seovendorco/sv-mcp
- **Docs:** https://seovendor.co/api/mcp

**Claude.ai and Claude Desktop:** Customize → Connectors → + → Add custom connector → paste `https://mcp.seovendor.co` → Connect and sign in to SV.

**Claude Code:**

```bash
claude mcp add --transport http sv-mcp https://mcp.seovendor.co
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{ "mcpServers": { "sv-mcp": { "url": "https://mcp.seovendor.co" } } }
```

Setup for VS Code, Windsurf and stdio-only clients, plus the full tool list, is in the [SV MCP README](https://github.com/seovendorco/sv-mcp#connect). SV MCP exposes the CLI's tools except `seo-image`, plus `get_task_status` and `get_task_result` for async tasks.

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
sv seogpt generate --type 18 --keyword "white label seo" --strict --format json --non-interactive
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
sv seogpt generate --type 18 --keyword "white label seo" --url https://example.com
sv geo-audit create-task --url https://example.com --keyword "seo agency,white label seo" --wait
sv image generate --keyword "white label seo" --type blog-header-image
sv top-competitors analyze --keyword "white label seo"
sv marketplace-services search --search "seo audit" --price 500 --category SEO
sv content-quality analyze --keyword "white label seo" --url https://example.com
```

Presets (shorthand commands for common seogpt operations):

```bash
sv meta  --keyword "white label seo" --url https://example.com
sv title --keyword "white label seo" --url https://example.com
```

> **Note:** `sv keywords`, `sv audit`, and `sv image` are group aliases, not standalone commands. They require an action: `sv keywords research --keyword "..."`, `sv audit create-task --url "..."`, `sv image generate --keyword "..."`.

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
| `prose` | `seogpt2`, `seo-gpt2` | `seogpt2` |
| `seogpt-compare` | `compare` | `seogptcompare` |
| `seo-mapping` | `mapping` | `seogptmapping` |
| `topical-authority` | `topical` | `topical-authority` |
| `top-competitors` | `competitors` | `top-competitors` |
| `marketplace-services` | `marketplace`, `services` | `marketplace-services` |
| `content-quality` | `quality`, `hcu-quality`, `eeat-quality` | `content-quality` |

The canonical API tool keys are discovered from the live API root; local aliases are only a human-friendly layer. For newly released tools, the CLI can also use adapter-provided endpoint hints until the API root advertises those tools. Root-discovered metadata still takes precedence.

## Enum resolution

For enum-heavy fields such as content type, content length, language, engine, image type, theme, background, color, and size, the CLI resolves values in this order:

1. Numeric ID exact match
2. Exact slug match
3. Exact canonical API value
4. Exact alias match
5. Exact label match
6. Normalized exact match
7. Prefix match
8. Contains match
9. Fuzzy match with safe thresholds

Examples that all resolve to Meta Description (id 18):

```bash
--type 18
--type meta-description
--type "Meta Description"
--type "meta desc"
```

`--length`/`--contentlength` (content length by ID, slug, or label — run `sv TOOL lengths` for valid values) resolves the same way:

```bash
sv seogpt generate --keyword "white label seo" --type 18 --length 300
```

> **Note:** Fuzzy matching is enabled by default. Use `--strict --no-fuzzy` in scripts to require exact ID or slug and avoid unintended matches.

Agent-safe mode:

```bash
sv seogpt generate --type 18 --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
```

## Options discovery

```bash
sv options list
sv options seogpt
sv options seogpt type --search meta
sv options seogpt contenttype --search meta
sv seogpt types --search meta
sv seogpt languages
sv seogpt engines
sv image themes --search wild
sv image types --search blog
```

## Raw API calls

Raw calls use live definitions only to find the selected tool endpoint. The payload is otherwise passed through unchanged except that `k` is injected when no API-key field already exists.

```bash
sv --format json call seogpt --json '{"action":"generate","kw":"white label seo","type":18}'
sv --format json call seogpt --file payload.json
cat payload.json | sv --format json call seogpt --stdin
```

The per-tool `raw` sub-command works the same way:

```bash
sv --format json seogpt raw --json '{"action":"generate","kw":"white label seo","type":18}'
```

> **Note:** `--format` must be placed before the tool name for both `sv call` and `sv TOOL raw` — it is a global flag owned by the root `sv` command, not by `call` or `raw`.

## Async task handling

For tools that return task IDs:

```bash
sv geo-audit create-task --url https://example.com --keyword "seo agency,white label seo" --wait
sv task status TASK_ID --tool geo-audit
sv task result TASK_ID --tool geo-audit
```

`prose` (formerly `seogpt2`) is another async tool. Its required field is `Topic` (a title or subject), mapped via `--topic` (`--title` is an alias for the same field). `--keyword`/`--kw` is a separate, optional field for additional keywords — it does not set the topic:

```bash
sv prose create-task --topic "White Label SEO for Agencies" --type on-page-blog-article --wait
```

See available types with `sv prose types`, lengths with `sv prose lengths`, engines with `sv prose engines`.

Manual 3-step flow (without `--wait`):

```bash
sv geo-audit create-task --url https://example.com --keyword "seo agency,white label seo"
sv geo-audit get-task-status --task-id TASK_ID
sv geo-audit get-result --task-id TASK_ID
```

> **Note:** `--format` is not available on `sv task status` or `sv task result` directly. Place it before `task` as a global flag:
>
> ```bash
> sv --format json task status TASK_ID
> sv --format json task result TASK_ID
> ```

If a task is created through the CLI, its tool mapping is stored in `~/.sv/tasks.json`, so `--tool` is usually optional later.

## Output formats

```bash
--format pretty     # default rich terminal output
--format json       # raw JSON (always works for any response)
--format table      # column table (list responses only)
--format csv        # CSV (list responses only)
--format markdown   # Markdown
--format text       # plain text (content/article responses)
```

Which format to use:

| Response type | Recommended formats |
|---|---|
| List results (keywords, competitors, services) | `table`, `csv` |
| Content / articles / generated text | `text`, `markdown` |
| Audit / analysis / nested data | `json`, `markdown` |
| Async task ID responses | `pretty` (default) |
| Any response | `json` (always safe) |

**Placement:** For tool commands (`sv seogpt generate`, `sv keywords research`, etc.), `--format` can go anywhere. For `sv call`, `sv options`, and `sv task`, `--format` must come before the subcommand:

```bash
sv seogpt generate --keyword "white label seo" --type 18 --format json   # works
sv --format json call seogpt --json '{"action":"generate","kw":"..."}'   # must be before call
```

Examples:

```bash
sv keywords research --keyword "white label seo" --format csv --output keywords.csv
sv geo-audit create-task --url https://example.com --keyword "seo agency,white label seo" --wait --format markdown --output audit.md
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

## Privacy

SV CLI runs on your computer and sends requests only to the SV API. It stores your API key in `~/.sv/config.json`, recent task IDs in `~/.sv/tasks.json`, and cached tool definitions in `~/.sv/cache/` (or under `SV_HOME` if set). There is no separate telemetry; requests carry an `X-SV-Client` header so the SV API can tell CLI usage apart from other clients.

See the SV privacy policy: https://seovendor.co/privacy-policy/

## Security

Never commit API keys, `.env`, or `~/.sv/config.json`. The repository `.gitignore` excludes common secret/config files. Report vulnerabilities using the process in `SECURITY.md`.
