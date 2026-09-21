# Changelog

## 0.8.0

- Automatically retries a request up to 3 times when the SV API returns HTTP 429 (rate limit of 1 request per second per API key), waiting as long as the `Retry-After` header asks. `--wait` polling keeps working under the limit.
- `APIError` now carries the HTTP `status_code` and the parsed response `data`, so callers such as SV MCP can show the API's own error message. CLI output is unchanged.
- README: corrected the clone URL; added "MCP server (SV MCP)" and "Privacy" sections.

## 0.3.0

- Renamed the distribution package from `seovendor-cli` to `sv-cli`.
- Renamed the console executable from `seovendor` to `sv`.
- Renamed the Python package from `seovendor_cli` to `sv_cli`.
- Updated documentation, examples, config paths, cache paths, and CI references for the SV brand.
- Changed the preferred environment variables to `SV_API_KEY` and `SV_HOME`.
- Retained `SEOVENDOR_API_KEY`, `SEOVENDOR_HOME`, and `~/.seovendor/config.json` as migration fallbacks.

## 0.2.0

- Added friendly command groups for `top-competitors`, `marketplace-services`, and `content-quality`.
- Added adapter fallback endpoint hints for newly released tools that are live before the API root advertises them.
- Added marketplace-friendly `--search`, `--price`, `--series`, and `--category` options.
- Added URL 1/URL 2 aliases for content quality comparisons.
- Added dynamic extraction of enum options from `Valid values:` descriptions in API definitions.

## 0.1.0

Initial public beta scaffold.

- Dynamic API root discovery and tool definitions cache
- Manual definitions refresh/list/show/clear commands
- API-key setup with auth commands and profile support
- Raw API call command
- Human-friendly enum resolver with strict/no-fuzzy modes
- Friendly command groups and aliases for 13 API tools
- Options discovery commands and tool-specific aliases
- Async task polling helpers
- JSON, pretty, table, CSV, markdown, and text output formatters
- Open-source repository files and CI scaffold
