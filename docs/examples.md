# Examples

## Keyword research

```bash
sv keywords research --keyword "white label seo" --country us --language en
sv keywords research --keyword "roof repair" --format csv --output keywords.csv
```

## SEO GPT

```bash
sv seogpt generate \
  --type "meta desc" \
  --keyword "white label seo" \
  --url https://example.com
```

## Raw API

```bash
sv call seogpt --json '{"action":"generate","kw":"white label seo","contenttype":15}' --format json
```

## File/stdin input

```bash
sv transform rewrite --file input.txt --output output.txt
cat article.txt | sv transform summarize --stdin
```

## Async tools

```bash
sv geo-audit run --url https://example.com --keywords "seo agency,white label seo" --wait --timeout 600 --poll-interval 5
```


## New API tools

```bash
sv top-competitors analyze --keyword "white label seo" --format table
sv marketplace-services search --search "seo audit" --price 500 --category SEO --format table
sv content-quality analyze --keyword "white label seo" --url https://example.com --url-b https://competitor.example --format markdown
```
