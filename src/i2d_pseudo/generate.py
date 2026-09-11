"""AI draft generation, pseudonym filtering, preview, and YAML rendering.

The only text ever handed to `generate_template` / an `AIProvider` is a
`SafeText` -- text that `replace.py` has already leak-checked. A draft's
keywords and field regexes are then filtered twice: anything containing a
pseudonym substring is dropped outright (never repaired -- a regex containing
a pseudonym is not safe to "fix up"), and anything left is dropped unless it
matches every real (un-pseudonymized) sample text.

Pure functions apart from the (mockable) AI provider call: no file I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

import yaml
from invoice2data.ai import AIProvider
from invoice2data.ai.template_generator import generate_template, preview_template

from .replace import SafeText
from .store import StoreEntry


def draft_template(
    safe_text: SafeText,
    *,
    provider: AIProvider | None = None,
    issuer: str | None = None,
) -> dict[str, Any]:
    """Draft a template from pseudonymized text.

    Args:
        safe_text (SafeText): Text that has passed the leak check.
        provider (AIProvider | None): Provider to use; the configured one
            when None.
        issuer (str | None): Optional issuer name to force into the template.

    Returns:
        dict[str, Any]: The raw draft (issuer/keywords/fields), not yet
            filtered against pseudonyms or real text.
    """
    return generate_template(safe_text.text, provider=provider, issuer=issuer)


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(needle and needle.lower() in lowered for needle in needles)


def drop_pseudonym_dependent(
    template: Mapping[str, Any], store: Mapping[str, StoreEntry]
) -> dict[str, Any]:
    """Drop any keyword/field that contains a pseudonym substring.

    Never "repairs" a keyword or regex that references a pseudonym -- it is
    dropped outright, per the project's fail-closed privacy rules.

    Args:
        template (Mapping[str, Any]): A draft template (issuer/keywords/
            exclude_keywords/fields).
        store (Mapping[str, StoreEntry]): The pseudonym store; only
            "replace" entries with a generated pseudonym are checked against.

    Returns:
        dict[str, Any]: A copy of ``template`` with tainted entries removed.
    """
    pseudonyms = [
        entry.pseudonym
        for entry in store.values()
        if entry.decision == "replace" and entry.pseudonym
    ]
    cleaned: dict[str, Any] = dict(template)
    cleaned["keywords"] = [
        kw for kw in cleaned.get("keywords", []) if not _contains_any(kw, pseudonyms)
    ]
    if "exclude_keywords" in cleaned:
        cleaned["exclude_keywords"] = [
            kw for kw in cleaned["exclude_keywords"] if not _contains_any(kw, pseudonyms)
        ]
    fields = {}
    for name, spec in cleaned.get("fields", {}).items():
        regex = spec["regex"] if isinstance(spec, dict) else spec
        if isinstance(regex, str) and _contains_any(regex, pseudonyms):
            continue
        fields[name] = spec
    cleaned["fields"] = fields
    return cleaned


def keep_matching_all(template: Mapping[str, Any], real_texts: Iterable[str]) -> dict[str, Any]:
    """Drop any keyword/field that doesn't match every given real text.

    Args:
        template (Mapping[str, Any]): A (pseudonym-filtered) draft template.
        real_texts (Iterable[str]): The real, un-pseudonymized sample texts.

    Returns:
        dict[str, Any]: A copy of ``template`` with non-matching entries
            removed.
    """
    texts = list(real_texts)
    kept: dict[str, Any] = dict(template)
    kept["keywords"] = [kw for kw in kept.get("keywords", []) if all(kw in t for t in texts)]
    fields = {}
    for name, spec in kept.get("fields", {}).items():
        regex = spec["regex"] if isinstance(spec, dict) else spec
        if not isinstance(regex, str):
            continue
        try:
            compiled = re.compile(regex)
        except re.error:
            continue
        if all(compiled.search(t) for t in texts):
            fields[name] = spec
    kept["fields"] = fields
    return kept


def preview(template: Mapping[str, Any], real_text: str) -> dict[str, str]:
    """Preview a template's field captures against real text.

    Args:
        template (Mapping[str, Any]): The (filtered) draft template.
        real_text (str): A real, un-pseudonymized sample text.

    Returns:
        dict[str, str]: Field name -> first captured value; missing fields
            are omitted.
    """
    return preview_template(dict(template), real_text)


_FIELD_ORDER = ("issuer", "keywords", "exclude_keywords", "fields", "options")


def render_yaml(template: Mapping[str, Any]) -> str:
    """Render a template as invoice2data-compatible YAML.

    Args:
        template (Mapping[str, Any]): The final, filtered template.

    Returns:
        str: YAML text ready to write to a ``.yml`` file.
    """
    ordered = {key: template[key] for key in _FIELD_ORDER if key in template}
    ordered.update({key: value for key, value in template.items() if key not in ordered})
    return yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True)
