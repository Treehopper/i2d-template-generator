from __future__ import annotations

from i2d_pseudo.candidates import Candidate
from i2d_pseudo.suggest import suggest


def _candidate(kind: str, key: str, context: str) -> Candidate:
    return Candidate(kind=kind, key=key, docs=frozenset({"doc"}), context=context)


def test_toll_free_prefix_defaults_to_keep() -> None:
    c = _candidate("phone", "08001234567", "Kundenservice erreichen Sie unter:")
    assert suggest(c) is False


def test_hotline_context_defaults_to_keep_even_without_toll_free_prefix() -> None:
    c = _candidate("phone", "0301234567", "Support-Hotline: 030 1234567")
    assert suggest(c) is False


def test_plain_personal_phone_defaults_to_replace() -> None:
    c = _candidate("phone", "030/1234567", "Telefon: 030 / 1234567")
    assert suggest(c) is True


def test_vendor_iban_context_defaults_to_keep() -> None:
    c = _candidate("iban", "DE1", "Unsere Bankverbindung: DE1...")
    assert suggest(c) is False


def test_customer_iban_defaults_to_replace() -> None:
    c = _candidate("iban", "DE1", "IBAN: DE1...")
    assert suggest(c) is True


def test_identity_and_id_kinds_default_to_replace() -> None:
    for kind in (
        "name",
        "name_part",
        "address",
        "email",
        "customer_number",
        "account_number",
        "contract_number",
        "mandate_id",
    ):
        assert suggest(_candidate(kind, "x", "")) is True
