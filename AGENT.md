# AGENT.md — SV CLI Agent Reference

SV CLI (`sv`) is a definition-driven command-line client for the SV AI API. It resolves human-friendly flags to live API field names and enum values at runtime. This file documents the patterns, tools, and response shapes an AI agent needs to call the CLI reliably.

---

## Authentication

Set the API key as an environment variable before all calls:

```bash
export SV_API_KEY="your-key-here"
```

Alternative — inline flag (avoid in shared environments):

```bash
sv seogpt generate --keyword "..." --type 18 --api-key "your-key-here" --format json
```

Never use `sv auth set` in agent context — it is interactive.

---

## Standard Agent Invocation Pattern

Always include these flags on every call:

```
sv TOOL ACTION --FLAG VALUE --strict --no-fuzzy --non-interactive --format json
```

| Flag | Purpose |
|---|---|
| `--strict` | Require exact enum ID or slug — no guessing |
| `--no-fuzzy` | Disable fuzzy matching — prevents unintended matches |
| `--non-interactive` | Disable all prompts — never blocks waiting for input |
| `--format json` | Machine-readable output — always parseable |

**`--format` placement rule:**
- Tool action commands (`sv seogpt generate`, `sv keywords research`, etc.) — `--format` can go anywhere
- `sv call`, `sv task`, `sv TOOL raw` — `--format` MUST go before the subcommand:

```bash
sv --format json call seogpt --json '{"action":"generate","kw":"...","type":18}'
sv --format json task status TASK_ID --tool geo-audit
sv --format json seogpt raw --json '{"action":"generate","kw":"...","type":18}'
```

---

## Tool Index

All 16 available tools. Use exact command names — aliases are human shortcuts.

| Command | Alias | Default Action | API Required Fields | Async |
|---|---|---|---|---|
| `better-keywords` | `keywords` | `research` / `filter` | `--keyword` (`filter` needs a JSON `data` array — raw call only) | No |
| `content-transformer` | `transform` | `rewrite` | `--text` | No |
| `core-analysis` | `core` | `analyze` | *(none required)* | No |
| `geo-audit` | `audit` | `create-task` | `--url` `--keyword` | Yes |
| `insight-igniter` | `insights` | `entities` | `--url` | No |
| `preliminary-audit` | `prelim-audit` | `analyze` | `--url` | No |
| `ranklens` | — | `rank` | `--entity` `--url` | No |
| `seo-image` | `image` | `generate` | `--keyword` | No |
| `seogpt` | `seo-gpt` | `generate` | `--keyword` `--type` | No |
| `seogpt2` | `seo-gpt2` | `create-task` | `--topic` *(`--keyword`/`--kw` is a separate, optional field)* | Yes |
| `seogpt-compare` | `compare` | `create-task` | `--url` `--keyword` | Yes |
| `seo-mapping` | `mapping` | `create-task` | `--url` `--keyword` | Yes |
| `topical-authority` | `topical` | `topics` | `--keyword` | No |
| `top-competitors` | `competitors` | `analyze` | `--keyword` | No |
| `marketplace-services` | `marketplace` | `search` | `--search` | No |
| `content-quality` | `quality` | `analyze` | `--keyword` `--url` | No |

### All actions per tool

```
better-keywords:      research, filter, raw
content-transformer:  rewrite, raw
core-analysis:        analyze, raw
geo-audit:            create-task, get-task-status, get-result, raw
insight-igniter:      entities, raw
preliminary-audit:    analyze, raw
ranklens:             rank, competitors, raw
seo-image:            generate, raw
seogpt:               generate, raw
seogpt2:              create-task, get-task-status, get-result, raw
seogpt-compare:       create-task, get-task-status, get-result, raw
seo-mapping:          create-task, get-task-status, get-result, raw
topical-authority:    topics, content, raw
top-competitors:      analyze, raw
marketplace-services: search, raw
content-quality:      analyze, raw
```

---

## Enum Discovery — Always Do This Before Calling

Never guess enum values for `--type`, `--language`, `--engine`, `--theme`, etc. Discover them first.

```bash
# List all option fields for a tool
sv options seogpt

# List all values for a specific field
sv options seogpt type

# Filter values by keyword
sv options seogpt type --search meta

# Shorthand subcommands (where available)
sv seogpt types
sv seogpt types --search meta
sv seogpt lengths
sv seogpt languages
sv seogpt engines
sv image types
sv image themes
sv image themes --search wild
sv seogpt2 types
sv seogpt2 lengths
sv seogpt2 languages
sv seogpt2 tones
sv seogpt2 engines
sv geo-audit types
sv geo-audit languages
sv seo-mapping types
sv better-keywords types
sv better-keywords languages
sv content-transformer types
sv content-transformer lengths
sv content-transformer languages
sv ranklens languages
sv ranklens engines
sv topical-authority modes
sv topical-authority languages
sv marketplace-services series
sv marketplace-services categories
```

Options output format (use `id` or `slug` with `--strict`):

```
label             slug              id
----------------  ----------------  ---
Meta Description  meta-description  18
Meta Keywords     meta-keywords     180
```

With `--strict --no-fuzzy`: use `--type 18` or `--type meta-description`. Never use label strings.

---

## JSON Response Structure

Every response follows this envelope:

```json
{
  "success": true,
  "application": "seogpt",
  "action": "generate",
  "data": { ... },
  "meta": { "upstream_http_code": 200, "duration_ms": 1234, "request_id": "..." },
  "error": null
}
```

On failure:
```json
{
  "success": false,
  "data": null,
  "error": { "code": "VALIDATION_ERROR", "message": "...", "field": "..." }
}
```

### Response data shapes by type

**Content response** (`seogpt generate`, `content-transformer rewrite`, `sv meta`, `sv title`):
```json
{ "data": { "text": "generated content here" } }
```
Parse: `response["data"]["text"]`

**List response** (`better-keywords research`, `top-competitors analyze`, `marketplace-services search`, `topical-authority topics`):
```json
{ "data": [ { "keyword": "...", "volume": 1000, ... }, ... ] }
```
Parse: `response["data"]` — array of objects

**Async task created** (`geo-audit create-task`, `seogpt2 create-task`, `seogpt-compare create-task`, `seo-mapping create-task`):
```json
{ "data": { "task_id": "wFEGe...", "status": "pending", "stage": "queued", "percent_complete": 1 } }
```
Parse: `response["data"]["task_id"]`

**Task status** (`get-task-status`):
```json
{ "data": { "task_id": "...", "status": "pending|processing|complete", "percent_complete": 75 } }
```
Done when: `status` is one of `done`, `complete`, `completed`, `success`, `finished`, `ready`

**Audit/analysis response** (`core-analysis`, `preliminary-audit`, `content-quality`, `ranklens`):
```json
{ "data": { ... nested object ... } }
```
Parse: `response["data"]`

---

## Async Task Workflow

Three patterns — choose one per use case.

### Pattern 1: `--wait` (simplest — blocks until done)

```bash
sv geo-audit create-task --url https://example.com --keyword "white label seo" --wait --strict --no-fuzzy --non-interactive --format json
```

Returns the final result directly. Default timeout: 600s. Override:
```bash
--wait --timeout 300 --poll-interval 10
```

### Pattern 2: Create then poll via `sv task`

```bash
# Step 1 — create
sv geo-audit create-task --url https://example.com --keyword "white label seo" --non-interactive --format json

# Step 2 — poll status (repeat until done)
sv --format json task status TASK_ID --tool geo-audit

# Step 3 — get result
sv --format json task result TASK_ID --tool geo-audit
```

`--tool` is required if the task was not created in the same session (local cache miss).

### Pattern 3: Direct tool polling

```bash
sv geo-audit get-task-status --task-id TASK_ID --format json
sv geo-audit get-result --task-id TASK_ID --format json
```

Same for `seogpt2`, `seogpt-compare`, `seo-mapping` — replace `geo-audit` with the tool name.

---

## Critical Field Exceptions

These differ from the standard pattern — get them wrong and the call fails.

### seogpt2 — `--topic` maps to `Topic` (required), `--keyword`/`--kw` is a separate field

```bash
# CORRECT — --topic sends value as the required "Topic" API field
sv seogpt2 create-task --topic "White Label SEO for Agencies" --type on-page-blog-article --wait --strict --no-fuzzy --non-interactive --format json

# --title is an alias for --topic (same field)
sv seogpt2 create-task --title "White Label SEO for Agencies" --type on-page-blog-article --wait --strict --no-fuzzy --non-interactive --format json

# --keyword/--kw maps to the separate, optional KW field — it does NOT set Topic
sv seogpt2 create-task --topic "White Label SEO for Agencies" --keyword "white label seo" --type on-page-blog-article --wait --strict --no-fuzzy --non-interactive --format json
```

### better-keywords `filter` — requires `data` array from prior `research` call

The `filter` action AI-filters a keyword list for relevance. No CLI flag maps to the `data` field — must use a raw call.

```bash
# Step 1 — research to get keyword array
sv keywords research --keyword "white label seo" --non-interactive --format json
# → parse response["data"]  (array of keyword objects)

# Step 2 — filter using that array via raw call
sv --format json call better-keywords --json '{"action":"filter","kw":"white label seo","data":[{"keyword":"...","volume":1000}]}'
```

### seogpt — `--contenttype` is an alias for `--type`

```bash
sv seogpt generate --keyword "..." --contenttype meta-description --strict --no-fuzzy --non-interactive --format json
```

### ranklens `competitors` — requires `mgptid` from prior `rank` response

No CLI flag exists for `mgptid`. Must use raw call:

```bash
# Step 1 — get MGPTID from rank response
sv ranklens rank --entity "white label seo" --url https://example.com --format json
# → parse response["data"]["MGPTID"]
# response["data"] always uses "entity", never "keyword" — --keyword/--kw still works as an input alias, but the response field name is always "entity"

# Step 2 — pass MGPTID via raw call
sv --format json call ranklens --json '{"action":"competitors","mgptid":"MGPTID_VALUE","web":"https://example.com","entity":"white label seo"}'
```

### `sv task status/result` — `--format` must be global

```bash
# CORRECT
sv --format json task status TASK_ID --tool geo-audit

# WRONG — --format not accepted here
sv task status TASK_ID --tool geo-audit --format json
```

---

## Common Errors and Recovery

| Error message | Cause | Fix |
|---|---|---|
| `Could not resolve --type "X" in strict mode` | Value is not a valid slug or ID | Run `sv options TOOL type` → use `id` or `slug` column |
| `Could not resolve --type "X"` (no strict) | No match found at any level | Run `sv options TOOL type --search X` to find closest match |
| `Topic is required` | seogpt2 called without `--topic` | Add `--topic "your topic"` |
| `task_id is invalid` | Task has expired on the server | Create a new task |
| `No local tool mapping found for task` | Task not in `~/.sv/tasks.json` | Add `--tool TOOL_NAME` explicitly |
| `API authentication failed: HTTP 401` | Bad or missing API key | Check `SV_API_KEY` environment variable |
| `API rate limit exceeded` | Too many requests | Wait and retry — add delay between calls |
| `No such option: --format` | `--format` placed after `call`/`task`/`raw` | Move `--format` before the subcommand |
| `Action must be rewrite` | Wrong action for content-transformer | Only `rewrite` is supported, not `summarize` |
| `Data must be a JSON array` | `better-keywords filter` called without `data` | Pass keyword array from prior `research` call via raw JSON |

---

## Raw JSON Fallback

When friendly flags are insufficient, send the payload directly. The CLI injects the API key automatically.

```bash
sv --format json call seogpt --json '{"action":"generate","kw":"white label seo","type":18}'
sv --format json call geo-audit --json '{"action":"createTask","kw":"white label seo","URL":"https://example.com"}'
sv --format json call ranklens --json '{"action":"competitors","mgptid":"...","web":"https://example.com","entity":"white label seo"}'
```

From a file:
```bash
sv --format json call seogpt --file payload.json
```

From stdin:
```bash
cat payload.json | sv --format json call seogpt --stdin
```

---

## Definitions and Schema Discovery

```bash
sv definitions list                    # all available tools + endpoints
sv definitions show seogpt             # full schema for one tool (api_input fields)
sv definitions refresh                 # force refresh from live API
sv options list                        # all tools with option set counts
```

Use `sv definitions show TOOL` to inspect all API input fields before building raw payloads.

---

## Quick Reference — One Call Per Tool

Agent-safe examples with exact IDs. Replace values as needed.

```bash
sv keywords research --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
# better-keywords filter requires keyword data from a prior research call — use raw call:
sv --format json call better-keywords --json '{"action":"filter","kw":"white label seo","data":[{"keyword":"white label seo","volume":1000}]}'
sv content-transformer rewrite --text "SEO services for agencies" --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
sv core-analysis analyze --url https://example.com --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
sv geo-audit create-task --url https://example.com --keyword "white label seo" --wait --strict --no-fuzzy --non-interactive --format json
sv insight-igniter entities --url https://example.com --strict --no-fuzzy --non-interactive --format json
sv preliminary-audit analyze --url https://example.com --strict --no-fuzzy --non-interactive --format json
sv ranklens rank --entity "white label seo" --url https://example.com --strict --no-fuzzy --non-interactive --format json
sv seo-image generate --keyword "white label seo" --type 33 --strict --no-fuzzy --non-interactive --format json
sv seogpt generate --keyword "white label seo" --type 18 --strict --no-fuzzy --non-interactive --format json
sv seogpt2 create-task --topic "White Label SEO for Agencies" --type 0 --wait --strict --no-fuzzy --non-interactive --format json
sv seogpt-compare create-task --url https://example.com --keyword "white label seo" --wait --strict --no-fuzzy --non-interactive --format json
sv seo-mapping create-task --url https://example.com --keyword "white label seo" --wait --strict --no-fuzzy --non-interactive --format json
sv topical-authority topics --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
sv top-competitors analyze --keyword "white label seo" --strict --no-fuzzy --non-interactive --format json
sv marketplace-services search --search "seo audit" --category SEO --strict --no-fuzzy --non-interactive --format json
sv content-quality analyze --keyword "white label seo" --url https://example.com --strict --no-fuzzy --non-interactive --format json
```

Common enum IDs (verify with `sv options` — these are from live API at time of writing):
- `seogpt --type 18` = Meta Description
- `seogpt --type 8` = Page Title
- `seo-image --type 33` = Blog Header Image
- `seogpt2 --type 0` = On-Page Blog Article
