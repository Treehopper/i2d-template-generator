from __future__ import annotations

import random

import pytest

from i2d_pseudo import pseudonyms, replace
from i2d_pseudo.store import StoreEntry


def test_spacing_variants_all_replaced() -> None:
    entries = [
        StoreEntry(kind="phone", key="5627464667", decision="replace", pseudonym="1928374650")
    ]
    text = "call 562 746 4667 or 5627464667 today"
    safe = replace.replace_document(text, entries)
    assert "5627464667" not in safe.text
    assert "562 746 4667" not in safe.text


def test_value_split_across_lines_is_replaced() -> None:
    entries = [
        StoreEntry(
            kind="iban",
            key="DE89370400440532013000",
            decision="replace",
            pseudonym="XX00000000000000000000",
        )
    ]
    text = "IBAN: DE89 3704\n0044 0532 0130 00\n"
    safe = replace.replace_document(text, entries)
    replace.check_no_leak(safe.text, entries)  # must not raise


def test_column_alignment_preserved_for_equal_length_replacement() -> None:
    entries = [
        StoreEntry(
            kind="customer_number", key="123456789", decision="replace", pseudonym="987654321"
        )
    ]
    text = "Kundennummer: 123456789   Vertragsnummer: 000"
    safe = replace.replace_document(text, entries)
    assert len(safe.text) == len(text)
    assert safe.text.startswith("Kundennummer: 987654321   Vertragsnummer:")


def test_keep_decision_leaves_text_untouched() -> None:
    entries = [
        StoreEntry(kind="iban", key="DE89370400440532013000", decision="keep", pseudonym=None)
    ]
    text = "IBAN: DE89 3704 0044 0532 0130 00"
    safe = replace.replace_document(text, entries)
    assert safe.text == text


def test_leak_detected_raises_and_never_includes_the_value() -> None:
    entries = [
        StoreEntry(kind="name", key="max mustermann", decision="replace", pseudonym="xyzabcdefghij")
    ]
    with pytest.raises(replace.LeakDetected) as excinfo:
        replace.check_no_leak("still says Max Mustermann here", entries)
    message = str(excinfo.value).lower()
    assert "max" not in message
    assert "mustermann" not in message


def test_leak_check_is_case_insensitive_for_text_kinds() -> None:
    entries = [
        StoreEntry(kind="name", key="max mustermann", decision="replace", pseudonym="xyzabcdefghij")
    ]
    with pytest.raises(replace.LeakDetected):
        replace.check_no_leak("MAX MUSTERMANN in caps", entries)


def test_rerun_with_existing_store_is_byte_identical() -> None:
    key = "max@example.com"
    pseudonym = pseudonyms.generate("email", key, random.Random(9))
    entries = [StoreEntry(kind="email", key=key, decision="replace", pseudonym=pseudonym)]
    text = "contact max@example.com now"
    first = replace.replace_document(text, entries)
    second = replace.replace_document(text, entries)
    assert first.text == second.text


def test_replace_document_raises_if_substitution_still_leaves_a_leak() -> None:
    # A pseudonym that (by bad luck) equals another selected value's key would
    # still get caught by the post-substitution check.
    entries = [
        StoreEntry(kind="mandate_id", key="ABC123", decision="replace", pseudonym="ABC123"),
    ]
    with pytest.raises(replace.LeakDetected):
        replace.replace_document("Mandatsreferenz: ABC123", entries)
