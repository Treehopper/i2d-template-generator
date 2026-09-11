"""Apply pseudonyms to extracted text and fail closed if anything leaks.

Both substitution and the leak check are driven by the same flexible pattern
built from a store entry's normalized ``key`` -- so "did we replace it" and
"is it really gone" can never disagree. The pattern tolerates arbitrary
whitespace (including line breaks) between characters (structured kinds) or
words (text kinds), and matches case-insensitively.

Column alignment (pdftotext ``-layout``) survives because a pseudonym is
always exactly as long, character-for-character, as the compact original it
was generated from (see `pseudonyms.py`); substitution reinserts each match's
own whitespace around that same-length fake.

Pure text transforms: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .store import StoreEntry

_TEXT_KINDS = frozenset({"name", "name_part", "address"})


class LeakDetected(RuntimeError):
    """Raised when a value selected for replacement is still present afterwards."""


@dataclass(frozen=True)
class SafeText:
    """Text that has passed the leak check.

    The only text representation that `generate.py` accepts -- real invoice
    text can never reach an ``AIProvider`` without going through here first.
    """

    text: str


def leak_pattern(kind: str, key: str) -> re.Pattern[str]:
    """Build a pattern matching any spacing/line-break variant of a key.

    Args:
        kind (str): Candidate kind; text kinds (name/name_part/address) match
            word-by-word, everything else character-by-character.
        key (str): The normalized (whitespace-collapsed) original value.

    Returns:
        re.Pattern[str]: A case-insensitive pattern.
    """
    if kind in _TEXT_KINDS:
        words = key.split()
        body = r"\s+".join(re.escape(word) for word in words)
    else:
        body = r"\s*".join(re.escape(ch) for ch in key)
    return re.compile(body, re.IGNORECASE)


def _reinsert_spacing(matched: str, compact_replacement: str) -> str:
    out = []
    index = 0
    for ch in matched:
        if ch.isspace():
            out.append(ch)
        else:
            out.append(compact_replacement[index])
            index += 1
    return "".join(out)


def apply_pseudonyms(text: str, entries: Iterable[StoreEntry]) -> str:
    """Substitute every "replace" entry's pattern with its pseudonym.

    Args:
        text (str): Source text.
        entries (Iterable[StoreEntry]): Store entries to apply; entries with
            ``decision != "replace"`` or no pseudonym are skipped.

    Returns:
        str: Text with matches replaced, spacing/layout preserved.
    """
    for entry in entries:
        if entry.decision != "replace" or entry.pseudonym is None:
            continue
        pattern = leak_pattern(entry.kind, entry.key)
        pseudonym = entry.pseudonym

        def _sub(match: re.Match[str], pseudonym: str = pseudonym) -> str:
            return _reinsert_spacing(match.group(0), pseudonym)

        text = pattern.sub(_sub, text)
    return text


def check_no_leak(text: str, entries: Iterable[StoreEntry]) -> None:
    """Fail closed if any "replace" entry's value is still present.

    Args:
        text (str): Text that was supposedly cleaned.
        entries (Iterable[StoreEntry]): Store entries to check.

    Raises:
        LeakDetected: If a selected value is still found, in any spacing, in
            any letter case. The message never includes the value itself.
    """
    for entry in entries:
        if entry.decision != "replace":
            continue
        if leak_pattern(entry.kind, entry.key).search(text):
            raise LeakDetected(
                f"a '{entry.kind}' value selected for replacement is still present "
                "after replacement; aborting"
            )


def replace_document(text: str, entries: Iterable[StoreEntry]) -> SafeText:
    """Apply pseudonyms to a document's text and verify nothing leaked.

    Args:
        text (str): Source text.
        entries (Iterable[StoreEntry]): Store entries to apply.

    Returns:
        SafeText: The pseudonymized text, cleared for use with an AIProvider.

    Raises:
        LeakDetected: See `check_no_leak`.
    """
    entries = list(entries)
    replaced = apply_pseudonyms(text, entries)
    check_no_leak(replaced, entries)
    return SafeText(replaced)
