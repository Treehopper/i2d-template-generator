"""Default yes/no suggestion per candidate, for the interactive selection step.

Candidate kinds detected under a shared label vocabulary can be either the
vendor's own data or the customer's (e.g. a "phone" candidate might be a
toll-free vendor hotline or the customer's own number) -- this module tells
those apart by context so the interactive prompt can default sensibly. The
user always has the final say; these are defaults, not decisions.

Pure heuristics over `Candidate` data: no I/O.
"""

from __future__ import annotations

from .candidates import Candidate

#: German toll-free / service number prefixes -- almost always a vendor hotline.
_VENDOR_PHONE_PREFIXES = ("0800", "00800", "0180")
_VENDOR_PHONE_CONTEXT_WORDS = ("hotline", "service", "fax", "zentrale", "support")
#: "Unsere Bankverbindung" (our bank details) marks the vendor's own IBAN.
_VENDOR_IBAN_CONTEXT_WORDS = ("unsere",)


def suggest(candidate: Candidate) -> bool:
    """Default yes/no for a candidate.

    Args:
        candidate (Candidate): The candidate to judge.

    Returns:
        bool: True to default to "replace" (personal data), False to default
            to "keep" (vendor's own data). Names, addresses, emails and
            per-customer id numbers default to "replace"; phone numbers and
            IBANs are judged by their surrounding context.
    """
    context = candidate.context.lower()
    if candidate.kind == "phone":
        if candidate.key.startswith(_VENDOR_PHONE_PREFIXES):
            return False
        if any(word in context for word in _VENDOR_PHONE_CONTEXT_WORDS):
            return False
        return True
    if candidate.kind == "iban":
        if any(word in context for word in _VENDOR_IBAN_CONTEXT_WORDS):
            return False
        return True
    return True
