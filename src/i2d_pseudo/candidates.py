"""Personal-data candidate detection.

Scans extracted invoice text for values that may need pseudonymizing: names,
addresses, IBANs, customer/account/contract numbers, phone numbers, mandate
references and emails. Detection is label/pattern driven and deliberately
narrow -- vendor-only identifiers (VAT id, creditor id / Gläubiger-ID) are not
in the label vocabulary at all, so they never become candidates. Kinds whose
label vocabulary is shared between vendor and customer use (e.g. a toll-free
"phone" number in a footer) are still detected here; distinguishing "keep" from
"replace" by context is `suggest.py`'s job, not this module's.

Pure text scanning: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from invoice2data.extract.candidates import find_identifiers


@dataclass(frozen=True)
class Candidate:
    """A personal-data candidate detected across one or more documents.

    Attributes:
        kind (str): Candidate category, e.g. "iban", "name", "phone".
        key (str): Normalized identity used for dedup and the store entry id
            ("kind:key") -- whitespace-collapsed, case-folded per kind.
        docs (frozenset[str]): Ids of the documents the candidate appeared in.
        context (str): A short label/line snippet for the interactive prompt.
    """

    kind: str
    key: str
    docs: frozenset[str]
    context: str


@dataclass(frozen=True)
class _Hit:
    kind: str
    value: str
    context: str


_TITLES = ("Herr", "Frau", "Familie")
_NAME_WORD = r"[A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]+"
_TITLE_GROUP = "|".join(_TITLES)
#: A name never spans multiple lines: words within it are joined by plain
#: spaces/tabs only, so a title on its own line (address block) can still be
#: followed by the name on the next line without swallowing the line after it.
_NAME_LINE = rf"{_NAME_WORD}(?:[ \t]+{_NAME_WORD}){{0,3}}"

_SALUTATION_RE = re.compile(
    rf"^(?:{_TITLE_GROUP})[ \t]*\n?[ \t]*(?:Dr\.[ \t]+)?({_NAME_LINE})$",
    re.MULTILINE,
)
_LETTER_SALUTATION_RE = re.compile(
    rf"Sehr geehrte[r]?[ \t]+(?:Herr|Frau)[ \t]+(?:Dr\.[ \t]+)?({_NAME_LINE})"
)

_STREET_RE = re.compile(
    r"\b([A-ZÄÖÜ][a-zäöüß]+(?:straße|strasse|weg|allee|platz|gasse|ring)\s?\d+\s?[a-zA-Z]?)\b"
)
#: Anchored to line start: a bare postal code elsewhere on the line (e.g. as
#: part of an invoice/document number) must not pair up with an unrelated
#: capitalized word later on the same line.
_ZIP_CITY_RE = re.compile(r"^(\d{5}\s+[A-ZÄÖÜ][a-zäöüß\-]+)\b", re.MULTILINE)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

#: Label -> candidate kind. Deliberately excludes vendor-only labels (VAT id,
#: "Gläubiger-ID" / creditor id) so those never become candidates.
_NUMBER_LABELS: dict[str, tuple[str, ...]] = {
    "customer_number": ("kundennummer", "kunden-nr", "customer no", "customer number", "kd.-nr"),
    "account_number": ("kontonummer", "konto-nr", "account number", "account no"),
    "contract_number": ("vertragsnummer", "vertrags-nr", "contract number", "contract no"),
    "mandate_id": ("mandatsreferenz", "mandats-referenz", "mandate reference", "sepa-mandat"),
    "phone": (
        "telefon",
        "tel.",
        "tel:",
        "tel nr",
        "rufnummer",
        "mobil",
        "fax",
        "hotline",
        "service-hotline",
        "servicenummer",
        "phone",
    ),
}

_VALUE_TAIL = r"\s*[:.]?\s*([0-9A-Za-z][0-9A-Za-z \-/.]{1,30}?)(?=\s{2,}|\n|$)"


def _label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(re.escape(label) + _VALUE_TAIL, re.IGNORECASE | re.MULTILINE)


def _line_context(text: str, pos: int, width: int = 60) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()[:width]


def _find_ibans(text: str) -> list[_Hit]:
    hits = []
    for cand in find_identifiers(text):
        if cand.kind != "iban":
            continue
        hits.append(_Hit("iban", cand.value, _line_context(text, cand.start)))
    return hits


def _find_emails(text: str) -> list[_Hit]:
    return [
        _Hit("email", match.group(), _line_context(text, match.start()))
        for match in _EMAIL_RE.finditer(text)
    ]


def _find_labeled_numbers(text: str) -> list[_Hit]:
    hits = []
    for kind, labels in _NUMBER_LABELS.items():
        for label in labels:
            for match in _label_pattern(label).finditer(text):
                value = match.group(1).strip(" .:-")
                if not re.search(r"\d{3,}", value):
                    continue
                hits.append(_Hit(kind, value, _line_context(text, match.start())))
    return hits


def _find_names(text: str) -> list[_Hit]:
    hits = []
    for pattern in (_SALUTATION_RE, _LETTER_SALUTATION_RE):
        for match in pattern.finditer(text):
            name = re.sub(r"\s+", " ", match.group(1)).strip()
            hits.append(_Hit("name", name, _line_context(text, match.start())))
    return hits


def _find_addresses(text: str) -> list[_Hit]:
    hits = []
    for pattern in (_STREET_RE, _ZIP_CITY_RE):
        for match in pattern.finditer(text):
            hits.append(_Hit("address", match.group(1), _line_context(text, match.start())))
    return hits


_DETECTORS: tuple[Callable[[str], list[_Hit]], ...] = (
    _find_ibans,
    _find_emails,
    _find_labeled_numbers,
    _find_names,
    _find_addresses,
)


def _normalize_key(kind: str, value: str) -> str:
    if kind == "iban":
        return re.sub(r"\s+", "", value).upper()
    if kind == "email":
        return re.sub(r"\s+", "", value).lower()
    if kind in ("name", "name_part", "address"):
        return re.sub(r"\s+", " ", value).strip().lower()
    return re.sub(r"\s+", "", value).upper()


def _expand_name_parts(hits: list[_Hit]) -> list[_Hit]:
    expanded = list(hits)
    for hit in hits:
        if hit.kind != "name":
            continue
        for word in hit.value.split():
            if len(word) >= 3:
                expanded.append(_Hit("name_part", word, hit.context))
    return expanded


def find_candidates(documents: Mapping[str, str]) -> list[Candidate]:
    """Detect personal-data candidates across one or more document texts.

    Args:
        documents (Mapping[str, str]): Document id -> extracted text.

    Returns:
        list[Candidate]: Deduplicated candidates, sorted by (kind, key). Each
            candidate's ``docs`` records every document it appeared in.
    """
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for doc_id, text in documents.items():
        hits: list[_Hit] = []
        for detector in _DETECTORS:
            hits.extend(detector(text))
        hits = _expand_name_parts(hits)
        for hit in hits:
            key = _normalize_key(hit.kind, hit.value)
            if not key:
                continue
            entry = merged.setdefault((hit.kind, key), {"docs": set(), "context": hit.context})
            entry["docs"].add(doc_id)
    return sorted(
        (
            Candidate(kind=kind, key=key, docs=frozenset(entry["docs"]), context=entry["context"])
            for (kind, key), entry in merged.items()
        ),
        key=lambda c: (c.kind, c.key),
    )
