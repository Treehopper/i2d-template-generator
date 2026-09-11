"""Format-preserving fake generation.

Given a normalized (whitespace-stripped) original value, produces a same-length
fake: digit runs become digit runs (leading zeros kept), letter runs become
letter runs (case kept), everything else (punctuation, an IBAN mask ``X``) is
kept as-is. Callers reinsert the original spacing/layout afterwards (see
``replace.py``); this module only ever sees compact strings.
"""

from __future__ import annotations

import random
import re
import string

_RUN_RE = re.compile(r"\d+|[A-Za-z]+|.", re.DOTALL)


def _random_digit_run(digits: str, rng: random.Random) -> str:
    leading_zeros = len(digits) - len(digits.lstrip("0"))
    rest_len = len(digits) - leading_zeros
    if rest_len == 0:
        return digits
    first = rng.randint(0, 9) if leading_zeros else rng.randint(1, 9)
    rest = "".join(str(rng.randint(0, 9)) for _ in range(rest_len - 1))
    return "0" * leading_zeros + str(first) + rest


def _random_letter_run(letters: str, rng: random.Random) -> str:
    return "".join(
        rng.choice(string.ascii_uppercase) if ch.isupper() else rng.choice(string.ascii_lowercase)
        for ch in letters
    )


def format_preserving(compact: str, rng: random.Random) -> str:
    """Generate a same-shape fake for a compact (no-whitespace) value.

    Digit runs are replaced with digit runs of the same length (leading zeros
    kept), letter runs with letter runs of the same length and case; any other
    character (punctuation, an IBAN mask ``X``) passes through unchanged.

    Args:
        compact (str): The original value with no whitespace.
        rng (random.Random): Source of randomness.

    Returns:
        str: A fake value of identical length and character shape.
    """
    parts = []
    for run in _RUN_RE.finditer(compact):
        token = run.group()
        if token.isdigit():
            parts.append(_random_digit_run(token, rng))
        elif token.isalpha():
            parts.append(_random_letter_run(token, rng))
        else:
            parts.append(token)
    return "".join(parts)


def _iban_check_digits(country: str, bban: str) -> str:
    rearranged = bban + country + "00"
    digits = "".join(str(int(char, 36)) for char in rearranged)
    return f"{98 - int(digits) % 97:02d}"


def generate_iban(compact_key: str, rng: random.Random) -> str:
    """Generate a fake IBAN of the same length, with a valid mod-97 checksum.

    The country code (first two letters) is kept. An ``X`` character (a masked
    digit in a partially-redacted IBAN) is kept as ``X`` and, in that case, the
    check digits are left as in the original since the true checksum cannot be
    computed from a partially masked number.

    Args:
        compact_key (str): The original IBAN with no whitespace, upper-cased.
        rng (random.Random): Source of randomness.

    Returns:
        str: A same-length fake IBAN.
    """
    country = compact_key[:2]
    bban_source = compact_key[4:]

    def _rand_char(ch: str) -> str:
        if ch == "X":
            return "X"
        if ch.isdigit():
            return str(rng.randint(0, 9))
        return rng.choice(string.ascii_uppercase)

    bban = "".join(_rand_char(ch) for ch in bban_source)
    if "X" in compact_key:
        check = compact_key[2:4]
    else:
        check = _iban_check_digits(country, bban)
    return country + check + bban


def compact_key(key: str) -> str:
    """Strip whitespace from a candidate's normalized key.

    ``Candidate.key`` / ``StoreEntry.key`` keep internal whitespace for text
    kinds (it is needed to build the word-boundary match pattern in
    `replace.py`); generation always needs the whitespace-free form so the
    result lines up 1:1 with every occurrence's own non-whitespace characters.

    Args:
        key (str): A candidate/store entry key.

    Returns:
        str: ``key`` with all whitespace removed.
    """
    return re.sub(r"\s+", "", key)


def generate(kind: str, key: str, rng: random.Random) -> str:
    """Generate a fake value for a candidate, dispatching by kind.

    Args:
        kind (str): Candidate kind, e.g. "iban", "name", "phone".
        key (str): The candidate's normalized key (whitespace is stripped
            internally, so callers may pass it as-is).
        rng (random.Random): Source of randomness.

    Returns:
        str: A same-length (whitespace-free) fake value.
    """
    compact = compact_key(key)
    if kind == "iban":
        return generate_iban(compact, rng)
    return format_preserving(compact, rng)
