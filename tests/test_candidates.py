from __future__ import annotations

from pathlib import Path

from i2d_pseudo import candidates, suggest

FIXTURE = (Path(__file__).parent / "fixtures" / "personal_data_invoice.txt").read_text(
    encoding="utf-8"
)


def _find(kind: str) -> dict[str, candidates.Candidate]:
    return {c.key: c for c in candidates.find_candidates({"doc": FIXTURE}) if c.kind == kind}


def test_customer_iban_detected_and_vendor_iban_detected_too() -> None:
    ibans = _find("iban")
    assert "DE89370400440532013000" in ibans  # customer's, for direct debit
    assert "DE12500105170648489890" in ibans  # vendor's own, footer


def test_vat_id_and_creditor_id_are_never_candidates() -> None:
    all_keys = {c.key for c in candidates.find_candidates({"doc": FIXTURE})}
    assert not any("DE123456789" in key for key in all_keys)  # USt-IdNr.
    assert not any("DE98ZZZ09999999999" in key for key in all_keys)  # Gläubiger-ID


def test_customer_number_detected() -> None:
    assert "123456789" in _find("customer_number")


def test_contract_number_detected() -> None:
    assert "987-654-321" in _find("contract_number")


def test_mandate_id_detected() -> None:
    assert "MREF-000111222" in _find("mandate_id")


def test_personal_phone_and_vendor_service_number_both_detected() -> None:
    phones = _find("phone")
    assert "030/1234567" in phones
    assert "08001234567" in phones


def test_email_detected() -> None:
    assert "max.mustermann@example.com" in _find("email")


def test_name_and_name_part_detected_with_title_stripped() -> None:
    names = _find("name")
    assert "max mustermann" in names
    assert "herr" not in names
    parts = _find("name_part")
    assert "max" in parts
    assert "mustermann" in parts
    assert "herr" not in parts


def test_street_and_zip_city_addresses_detected() -> None:
    addresses = _find("address")
    assert "beispielweg 12" in addresses
    assert "12345 musterstadt" in addresses


def test_zip_city_regex_does_not_cross_unrelated_columns() -> None:
    # Regression: a bare 5-digit run inside an invoice number must not pair up
    # with an unrelated capitalized word later on the same line.
    text = "Rechnung Nr. 2024-00147            Datum: 01.03.2024\n"
    result = candidates.find_candidates({"doc": text})
    assert not any(c.kind == "address" for c in result)


def test_docs_field_tracks_every_document_a_candidate_appeared_in() -> None:
    result = candidates.find_candidates({"a.pdf": FIXTURE, "b.pdf": FIXTURE})
    email = next(c for c in result if c.kind == "email")
    assert email.docs == frozenset({"a.pdf", "b.pdf"})


def test_candidate_not_present_in_only_one_of_several_docs() -> None:
    other = "Nothing personal here.\nGesamtbetrag: 1,00 EUR\n"
    result = candidates.find_candidates({"a.pdf": FIXTURE, "b.pdf": other})
    email = next(c for c in result if c.kind == "email")
    assert email.docs == frozenset({"a.pdf"})


def test_suggest_defaults_match_vendor_vs_personal_context() -> None:
    result = {(c.kind, c.key): c for c in candidates.find_candidates({"doc": FIXTURE})}
    assert suggest.suggest(result[("phone", "030/1234567")]) is True
    assert suggest.suggest(result[("phone", "08001234567")]) is False
    assert suggest.suggest(result[("iban", "DE89370400440532013000")]) is True
    assert suggest.suggest(result[("iban", "DE12500105170648489890")]) is False
