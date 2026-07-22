"""Human-friendly enum and field resolution."""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .adapters import field_candidates
from .errors import AmbiguousMatchError, InvalidInputError
from .utils import compact_text, normalize_text, slugify

OPTION_CONTAINER_KEYS = {
    "options",
    "values",
    "enum",
    "enums",
    "choices",
    "items",
    "list",
    "data",
}

ID_KEYS = ("id", "ID", "Id", "value", "Value", "key", "Key", "code", "Code", "enum", "enum_value")
LABEL_KEYS = (
    "label",
    "Label",
    "name",
    "Name",
    "title",
    "Title",
    "text",
    "Text",
    "display",
    "Display",
    "description",
    "Description",
)
SLUG_KEYS = ("slug", "Slug", "handle", "Handle")
ALIAS_KEYS = ("aliases", "alias", "synonyms", "shortcuts", "examples")
PARAM_NAME_KEYS = ("name", "field", "param", "parameter", "key")
VALID_VALUES_PATTERN = re.compile(r"valid values?\s*:\s*([^\n.]+(?:\.[^\n]*)?)", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    field: str
    id: Any
    label: str
    slug: str
    aliases: tuple[str, ...] = ()
    description: str | None = None
    raw: Any = None

    @property
    def canonical_value(self) -> Any:
        return self.id

    def searchable_values(self) -> list[str]:
        values = [str(self.id), self.slug, self.label, *self.aliases]
        if self.description:
            values.append(self.description)
        return [v for v in values if v]


def extract_option_sets(definition: Any) -> dict[str, list[Candidate]]:
    """Discover option/enum lists from a schema-free definitions payload.

    The SV definitions may evolve. This function deliberately looks for
    common JSON patterns instead of relying on one fixed schema.
    """

    found: dict[str, list[Candidate]] = {}

    def add(field: str, candidates: Iterable[Candidate]) -> None:
        clean_field = normalize_field(field)
        if not clean_field:
            return
        unique: dict[tuple[str, str, str], Candidate] = {}
        for candidate in candidates:
            key = (str(candidate.id), candidate.slug, candidate.label)
            unique[key] = Candidate(
                field=clean_field,
                id=candidate.id,
                label=candidate.label,
                slug=candidate.slug,
                aliases=candidate.aliases,
                description=candidate.description,
                raw=candidate.raw,
            )
        if not unique:
            return
        existing = found.setdefault(clean_field, [])
        seen = {(str(c.id), c.slug, c.label) for c in existing}
        for key, candidate in unique.items():
            if key not in seen:
                existing.append(candidate)

    def visit(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            # A mapping like {"15": "Meta Description", "32": "Product Description"}.
            mapping_candidates = candidates_from_mapping(path[-1] if path else "options", node)
            if mapping_candidates and len(mapping_candidates) >= 2:
                add(path[-1] if path else "options", mapping_candidates)

            for key, value in node.items():
                key_str = str(key)
                if isinstance(value, list):
                    field = path[-1] if key_str.lower() in OPTION_CONTAINER_KEYS and path else key_str
                    candidates = candidates_from_list(field, value)
                    if candidates:
                        add(field, candidates)
                elif isinstance(value, dict):
                    if key_str.lower() in OPTION_CONTAINER_KEYS and path:
                        candidates = candidates_from_mapping(path[-1], value)
                        if candidates:
                            add(path[-1], candidates)
                    else:
                        nested_candidates = candidates_from_mapping(key_str, value)
                        if nested_candidates and len(nested_candidates) >= 2:
                            add(key_str, nested_candidates)
                    visit(value, [*path, key_str])
                else:
                    continue
        elif isinstance(node, list):
            if path:
                candidates = candidates_from_list(path[-1], node)
                if candidates:
                    add(path[-1], candidates)
            for item in node:
                visit(item, path)

    def visit_described_options(node: Any) -> None:
        if isinstance(node, dict):
            field_name = first_present(node, PARAM_NAME_KEYS)
            description = first_present(node, ("description", "Description", "help", "Help"))
            if isinstance(field_name, str):
                if isinstance(description, list):
                    described_candidates = candidates_from_labeled_list(field_name, description)
                else:
                    described_candidates = candidates_from_valid_values(field_name, description)
                if described_candidates:
                    add(field_name, described_candidates)
            for value in node.values():
                visit_described_options(value)
        elif isinstance(node, list):
            for item in node:
                visit_described_options(item)

    visit(definition, [])
    visit_described_options(definition)
    return found


def extract_parameter_names(definition: Any) -> set[str]:
    names: set[str] = set()

    def visit(node: Any, parent_key: str | None = None) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_str = str(key)
                names.add(normalize_field(key_str))
                if key_str in PARAM_NAME_KEYS and isinstance(value, str):
                    names.add(normalize_field(value))
                visit(value, key_str)
        elif isinstance(node, list):
            for item in node:
                visit(item, parent_key)

    target = definition.get("api_input", definition) if isinstance(definition, dict) else definition
    visit(target)
    return {name for name in names if name}


def candidates_from_list(field: str, values: list[Any]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for item in values:
        candidate = candidate_from_item(field, item)
        if candidate:
            candidates.append(candidate)
    return candidates


def candidates_from_mapping(field: str, mapping: dict[Any, Any]) -> list[Candidate]:
    if not mapping:
        return []
    candidates: list[Candidate] = []
    for key, value in mapping.items():
        # Avoid turning arbitrary schema objects into options.
        if str(key) in {"type", "required", "optional", "parameters", "properties", "description"}:
            return []
        if isinstance(value, (str, int, float, bool)):
            label = str(value)
            candidates.append(
                Candidate(field=field, id=coerce_id(key), label=label, slug=slugify(label), raw={key: value})
            )
        elif isinstance(value, dict):
            candidate = candidate_from_item(field, {"id": key, **value})
            if candidate:
                candidates.append(candidate)
        else:
            return []
    return candidates


def candidate_from_item(field: str, item: Any) -> Candidate | None:
    if isinstance(item, (str, int, float, bool)):
        label = str(item)
        return Candidate(field=field, id=coerce_id(item), label=label, slug=slugify(label), raw=item)
    if not isinstance(item, dict):
        return None

    # API parameter definition objects such as {"field": "kw", "type": "string",
    # "description": "..."} are not enum candidates. Valid values embedded in
    # descriptions are extracted separately by extract_option_sets().
    lowered_keys = {str(key).lower() for key in item}
    enumish_keys = {"id", "value", "slug", "aliases", "options", "values", "enum", "choices"}
    if "field" in lowered_keys and "type" in lowered_keys and not (lowered_keys & enumish_keys):
        return None

    identifier = first_present(item, ID_KEYS)
    label = first_present(item, LABEL_KEYS)
    slug = first_present(item, SLUG_KEYS)
    description = first_present(item, ("description", "Description", "help", "Help"))
    aliases_raw = first_present(item, ALIAS_KEYS)
    aliases = normalize_aliases(aliases_raw)

    if identifier is None and slug is not None:
        identifier = slug
    if label is None and slug is not None:
        label = str(slug).replace("-", " ").replace("_", " ").title()
    if label is None and identifier is not None:
        label = str(identifier)
    if identifier is None and label is not None:
        identifier = slugify(label)
    if label is None or identifier is None:
        return None
    slug_value = str(slug) if slug is not None else slugify(label)

    # Include string identifiers as aliases when they differ from the label/slug.
    extra_aliases = []
    if isinstance(identifier, str) and identifier not in {label, slug_value}:
        extra_aliases.append(identifier)
    all_aliases = tuple(dict.fromkeys([*aliases, *extra_aliases]))

    return Candidate(
        field=field,
        id=coerce_id(identifier),
        label=str(label),
        slug=slugify(slug_value),
        aliases=all_aliases,
        description=str(description) if description is not None else None,
        raw=item,
    )


def candidates_from_valid_values(field: str, description: Any) -> list[Candidate]:
    text = description_to_text(description)
    if not text:
        return []
    match = VALID_VALUES_PATTERN.search(text)
    if not match:
        return []
    values_text = match.group(1)
    # Stop at the first sentence when the definitions include prose after the list.
    values_text = values_text.split(".", 1)[0]
    values = [part.strip().strip(".:") for part in values_text.split(",")]
    candidates: list[Candidate] = []
    for value in values:
        if not value:
            continue
        candidates.append(Candidate(field=field, id=value, label=value, slug=slugify(value), raw=value))
    return candidates


def candidates_from_labeled_list(field: str, items: list[Any]) -> list[Candidate]:
    """Parse ``"id: label"`` strings from an api_input description list."""
    candidates: list[Candidate] = []
    for item in items:
        if not isinstance(item, str):
            continue
        m = re.match(r"^(\S+)\s*:\s*(.+)$", item.strip())
        if not m:
            continue
        id_str, label = m.group(1).strip(), m.group(2).strip()
        candidates.append(Candidate(field=field, id=coerce_id(id_str), label=label, slug=slugify(label), raw=item))
    return candidates if len(candidates) >= 2 else []


def description_to_text(description: Any) -> str:
    if description is None:
        return ""
    if isinstance(description, str):
        return description
    if isinstance(description, (list, tuple, set)):
        return "\n".join(str(item) for item in description)
    return str(description)


def first_present(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def normalize_aliases(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        # Keep phrases intact where possible, but support comma/pipe-separated aliases.
        parts = [part.strip() for part in value.replace("|", ",").split(",")]
        return tuple(part for part in parts if part)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value),)


def coerce_id(value: Any) -> Any:
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def normalize_field(field: str) -> str:
    return str(field).strip().replace("-", "_").replace(" ", "_").lower()


def real_field_names(definition: Any) -> set[str]:
    """Normalized API field names that genuinely appear in a tool's live api_input.

    Used to decide which generic CLI options are relevant to a specific tool,
    so --help doesn't advertise flags the tool's real API doesn't accept.
    """

    names: set[str] = set()
    items = definition.get("api_input") if isinstance(definition, dict) else None
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, dict):
            field = item.get("field")
            if isinstance(field, str):
                names.add(normalize_field(field))
    return names


def is_cli_field_relevant(tool: str, cli_field: str, definition: Any) -> bool:
    """True when a generic CLI field resolves to a real field on this tool's live definition.

    When no live definition is cached yet (e.g. before the first `sv definitions
    refresh`, or offline), returns True for everything - never hide options based
    on missing data.
    """

    if not definition:
        return True
    api_field, _candidates = resolve_api_field(tool, cli_field, definition)
    target_fields = real_field_names(definition) | set(extract_option_sets(definition))
    return api_field in target_fields


def resolve_api_field(tool: str, cli_field: str, definition: Any) -> tuple[str, list[Candidate] | None]:
    """Choose the best API field name for a friendly CLI field."""

    option_sets = extract_option_sets(definition)
    parameter_names = extract_parameter_names(definition)
    candidates = field_candidates(tool, cli_field)
    normalized_candidates = [normalize_field(candidate) for candidate in candidates]

    for candidate in normalized_candidates:
        if candidate in option_sets:
            return candidate, option_sets[candidate]
    for candidate in normalized_candidates:
        if candidate in parameter_names:
            return candidate, option_sets.get(candidate)
    # Fall back by normalized compact comparison.
    compact_candidates = {compact_text(candidate): candidate for candidate in normalized_candidates}
    for existing_field in option_sets:
        if compact_text(existing_field) in compact_candidates:
            return existing_field, option_sets[existing_field]
    for existing_field in parameter_names:
        if compact_text(existing_field) in compact_candidates:
            return existing_field, option_sets.get(existing_field)
    return normalized_candidates[0] if normalized_candidates else normalize_field(cli_field), None


def resolve_enum_value(
    field: str,
    value: Any,
    candidates: list[Candidate],
    *,
    strict: bool = False,
    fuzzy: bool = True,
    non_interactive: bool = False,
) -> Any:
    """Resolve a user value into the candidate's canonical API value."""

    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [
            resolve_enum_value(field, item, candidates, strict=strict, fuzzy=fuzzy, non_interactive=non_interactive)
            for item in value
        ]
    text = str(value).strip()
    if not text:
        raise InvalidInputError(f'Could not resolve --{field}: empty value.')

    # 1. Numeric ID exact match.
    if text.isdigit():
        numeric = int(text)
        numeric_matches = [candidate for candidate in candidates if candidate.id == numeric]
        if len(numeric_matches) == 1:
            return numeric_matches[0].canonical_value
        if len(numeric_matches) > 1:
            raise ambiguous_error(field, text, numeric_matches)

    # 2. Exact slug match.
    slug_matches = [candidate for candidate in candidates if str(candidate.slug) == text]
    if len(slug_matches) == 1:
        return slug_matches[0].canonical_value
    if len(slug_matches) > 1:
        raise ambiguous_error(field, text, slug_matches)

    # 3. Exact canonical API value match. This covers string-valued enums.
    canonical_matches = [candidate for candidate in candidates if str(candidate.id) == text]
    if len(canonical_matches) == 1:
        return canonical_matches[0].canonical_value
    if len(canonical_matches) > 1:
        raise ambiguous_error(field, text, canonical_matches)

    if strict:
        allowed = ", ".join(format_candidate(candidate) for candidate in candidates[:10])
        raise InvalidInputError(
            f'Could not resolve --{field} "{text}" in strict mode. Use a numeric ID, exact slug, '
            f"or exact canonical API value. Examples: {allowed}"
        )

    # 4. Exact alias/label matches are intentionally non-strict.
    exact_groups = [
        lambda c: text in {str(alias) for alias in c.aliases},
        lambda c: str(c.label) == text,
    ]
    for matcher in exact_groups:
        matches = [candidate for candidate in candidates if matcher(candidate)]
        if len(matches) == 1:
            return matches[0].canonical_value
        if len(matches) > 1:
            raise ambiguous_error(field, text, matches)

    norm = normalize_text(text)
    compact = compact_text(text)

    # 5. Normalized exact match.
    normalized_matches = [
        candidate
        for candidate in candidates
        if any(normalize_text(value) == norm or compact_text(value) == compact for value in candidate.searchable_values())
    ]
    if len(normalized_matches) == 1:
        return normalized_matches[0].canonical_value
    if len(normalized_matches) > 1:
        raise ambiguous_error(field, text, normalized_matches)

    # 6. Prefix match.
    prefix_matches = [
        candidate
        for candidate in candidates
        if any(normalize_text(value).startswith(norm) or compact_text(value).startswith(compact) for value in candidate.searchable_values())
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0].canonical_value
    if len(prefix_matches) > 1:
        raise ambiguous_error(field, text, prefix_matches)

    # 7. Contains match.
    contains_matches = [
        candidate
        for candidate in candidates
        if any(norm in normalize_text(value) or compact in compact_text(value) for value in candidate.searchable_values())
    ]
    if len(contains_matches) == 1:
        return contains_matches[0].canonical_value
    if len(contains_matches) > 1:
        raise ambiguous_error(field, text, contains_matches)

    # 8. Fuzzy match.
    if fuzzy:
        scored = sorted(
            ((best_score(text, candidate), candidate) for candidate in candidates),
            key=lambda pair: pair[0],
            reverse=True,
        )
        if scored:
            best, best_candidate = scored[0]
            second = scored[1][0] if len(scored) > 1 else 0
            if best >= 95 or (best >= 85 and best - second >= 10):
                return best_candidate.canonical_value
            if best >= 70:
                raise ambiguous_error(field, text, [candidate for score, candidate in scored[:5] if score >= 70])

    suggestions = ", ".join(format_candidate(candidate) for candidate in candidates[:10])
    raise InvalidInputError(
        f'Could not resolve --{field} "{text}". Try `sv options TOOL {field} --search {text}`. '
        f"Examples: {suggestions}"
    )


def best_score(text: str, candidate: Candidate) -> float:
    norm = normalize_text(text)
    compact = compact_text(text)
    scores = []
    for value in candidate.searchable_values():
        scores.append(100 * difflib.SequenceMatcher(None, norm, normalize_text(value)).ratio())
        scores.append(100 * difflib.SequenceMatcher(None, compact, compact_text(value)).ratio())
    return max(scores or [0.0])


def ambiguous_error(field: str, value: str, matches: list[Candidate]) -> AmbiguousMatchError:
    lines = [f'Error: Could not resolve --{field} "{value}".', "It matched multiple options:"]
    for index, candidate in enumerate(matches[:10], start=1):
        lines.append(f"{index}. {format_candidate(candidate)}")
    lines.append("Please rerun with one of:")
    for candidate in matches[:5]:
        lines.append(f"--{field} {candidate.slug}")
    return AmbiguousMatchError("\n".join(lines))


def format_candidate(candidate: Candidate) -> str:
    return f"{candidate.label} {candidate.slug} id: {candidate.id}"


def search_candidates(candidates: list[Candidate], query: str | None) -> list[Candidate]:
    if not query:
        return candidates
    norm = normalize_text(query)
    compact = compact_text(query)
    filtered = []
    for candidate in candidates:
        if any(norm in normalize_text(value) or compact in compact_text(value) for value in candidate.searchable_values()):
            filtered.append(candidate)
    if filtered:
        return filtered
    scored = sorted(
        ((best_score(query, candidate), candidate) for candidate in candidates),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [candidate for score, candidate in scored if score >= 60][:20]
