# API Definition Format

The CLI intentionally does not assume a single rigid definition schema. It fetches the API root, then each tool's definitions URL.

Expected root shape:

```json
{
  "seogpt": {
    "Endpoint": "https://ai.seovendor.co/api/seogpt/",
    "Definitions": "https://ai.seovendor.co/api/seogpt/definitions"
  }
}
```

The resolver searches definitions recursively for common enum/option patterns, including:

```json
{
  "contenttype": {
    "options": [
      {"id": 15, "label": "Meta Description", "slug": "meta-description", "aliases": ["meta desc"]}
    ]
  }
}
```

Accepted candidate fields include IDs/values, labels/names/titles, slugs, aliases, synonyms, descriptions, and mapping-style enums such as:

```json
{
  "contenttype": {
    "15": "Meta Description",
    "32": "Product Description"
  }
}
```
