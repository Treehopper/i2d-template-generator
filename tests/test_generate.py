from __future__ import annotations

from typing import Any

import yaml

from i2d_pseudo import generate, replace
from i2d_pseudo.store import StoreEntry


class RecordingProvider:
    """Stub AIProvider that records everything it was sent, for leak assertions."""

    name = "mock"

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.texts: list[str] = []
        self.instructions: list[str | None] = []

    def is_available(self) -> bool:
        return True

    def extract_structured(
        self, text: str, json_schema: dict[str, Any], *, instructions: str | None = None
    ) -> dict[str, Any]:
        self.texts.append(text)
        self.instructions.append(instructions)
        return dict(self._response)


REAL_NAME = "Max Mustermann"
PSEUDONYM = "gviwvuctufrxh"


def test_provider_never_receives_real_text_or_instructions() -> None:
    provider = RecordingProvider({"keywords": ["Fake Corp"], "fields": {}})
    safe = replace.SafeText(f"Fake Corp\n{PSEUDONYM}\nGesamtbetrag: 123,45 EUR\n")
    generate.draft_template(safe, provider=provider)
    assert len(provider.texts) == 1
    assert REAL_NAME not in provider.texts[0]
    for instructions in provider.instructions:
        assert instructions is None or REAL_NAME not in instructions


def test_draft_template_only_accepts_safe_text() -> None:
    # SafeText is the only text type generate.py's functions take -- a plain
    # str is a type error, enforced by mypy; this just documents the contract.
    provider = RecordingProvider({"keywords": [], "fields": {}})
    safe = replace.SafeText("clean text")
    generate.draft_template(safe, provider=provider)
    assert provider.texts == ["clean text"]


def test_pseudonym_dependent_keyword_and_field_are_dropped_not_repaired() -> None:
    store = {
        "name:x": StoreEntry(kind="name", key="x", decision="replace", pseudonym=PSEUDONYM),
    }
    draft = {
        "keywords": ["Fake Corp", PSEUDONYM],
        "fields": {
            "amount": r"Gesamtbetrag:\s+([\d,]+)\s+EUR",
            "leaky_field": rf"({PSEUDONYM})",
        },
    }
    cleaned = generate.drop_pseudonym_dependent(draft, store)
    assert cleaned["keywords"] == ["Fake Corp"]
    assert "leaky_field" not in cleaned["fields"]
    assert "amount" in cleaned["fields"]


def test_keep_matching_all_requires_every_real_text_to_match() -> None:
    draft = {
        "keywords": ["Fake Corp", "Only In One Sample"],
        "fields": {"amount": r"(\d+,\d\d)"},
    }
    real_texts = ["Fake Corp 12,34", "Fake Corp 56,78"]
    kept = generate.keep_matching_all(draft, real_texts)
    assert kept["keywords"] == ["Fake Corp"]
    assert "amount" in kept["fields"]


def test_keep_matching_all_drops_a_field_regex_that_fails_on_one_sample() -> None:
    draft = {"keywords": [], "fields": {"amount": r"Total:\s+(\d+,\d\d)"}}
    real_texts = ["Total: 12,34", "no total mentioned here"]
    kept = generate.keep_matching_all(draft, real_texts)
    assert "amount" not in kept["fields"]


def test_preview_returns_captured_values_from_real_text() -> None:
    template = {"fields": {"amount": r"Total:\s+(\d+,\d\d)"}}
    preview = generate.preview(template, "Total: 42,00")
    assert preview == {"amount": "42,00"}


def test_render_yaml_round_trips_and_orders_known_fields_first() -> None:
    template = {
        "fields": {"amount": r"Total:\s+(\d+,\d\d)"},
        "issuer": "Fake Corp",
        "keywords": ["Fake Corp"],
    }
    rendered = generate.render_yaml(template)
    assert yaml.safe_load(rendered) == template
    assert rendered.index("issuer:") < rendered.index("keywords:") < rendered.index("fields:")
