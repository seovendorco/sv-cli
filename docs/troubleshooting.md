# Troubleshooting

## Missing API key

```text
Error: Missing SV API key.
```

Fix:

```bash
sv auth set
# or
export SV_API_KEY="..."
```

## Definitions cannot be fetched

Try:

```bash
sv definitions refresh --debug
```

If stale cache exists, the CLI will use it with a warning. To force a clean fetch:

```bash
sv definitions clear
sv definitions refresh
```

## Ambiguous enum value

Use options discovery:

```bash
sv options seogpt contenttype --search description
```

Then rerun with an exact slug or ID.

## CSV output fails

CSV output requires tabular API response data, usually a list of records under keys such as `keywords`, `results`, `items`, `rows`, or `data`.


## Legacy config

After the rename, the default config and cache directory is `~/.sv`. If `~/.sv/config.json` does not exist but `~/.seovendor/config.json` does, the CLI reads the legacy config as a migration fallback.
