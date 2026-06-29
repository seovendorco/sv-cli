# Commands

## Global commands

```bash
sv auth
sv profile
sv config
sv definitions
sv options
sv task
sv call
```

## Tool groups

```bash
sv better-keywords research --keyword "white label seo"
sv content-transformer rewrite --text "Original content"
sv core-analysis analyze --url https://example.com
sv geo-audit run --url https://example.com --keywords "seo agency" --wait
sv insight-igniter generate --keyword "white label seo"
sv preliminary-audit run --url https://example.com
sv ranklens analyze --brand "SV" --keyword "white label seo"
sv seo-image generate --keyword "white label seo" --type blog-header
sv seogpt generate --type meta-description --keyword "white label seo"
sv seogpt2 article --keyword "white label seo" --wait
sv seogpt-compare run --url https://example.com --keyword "white label seo"
sv seo-mapping run --url https://example.com --keywords "seo agency" --wait
sv topical-authority generate --keyword "local seo"
sv top-competitors analyze --keyword "white label seo"
sv marketplace-services search --search "seo audit" --price 500 --category SEO
sv content-quality analyze --keyword "white label seo" --url https://example.com --url-b https://competitor.example
```

All tool commands accept unknown `--param value` pairs, which are forwarded to the API payload after definition-driven field and enum resolution where possible.
