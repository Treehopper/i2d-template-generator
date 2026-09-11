from __future__ import annotations

import random

from invoice2data.extract.validators import validate_iban

from i2d_pseudo import pseudonyms


def test_format_preserving_keeps_length_and_character_shape() -> None:
    rng = random.Random(1)
    original = "Max-Mustermann12b"
    fake = pseudonyms.format_preserving(original, rng)
    assert len(fake) == len(original)
    for orig_ch, fake_ch in zip(original, fake, strict=True):
        if orig_ch.isdigit():
            assert fake_ch.isdigit()
        elif orig_ch.isalpha():
            assert fake_ch.isalpha()
            assert fake_ch.isupper() == orig_ch.isupper()
        else:
            assert fake_ch == orig_ch


def test_format_preserving_keeps_leading_zeros() -> None:
    fake = pseudonyms.format_preserving("00123456", random.Random(2))
    assert fake.startswith("00")
    assert len(fake) == 8


def test_format_preserving_never_introduces_a_spurious_leading_zero() -> None:
    for seed in range(200):
        fake = pseudonyms.format_preserving("9123456", random.Random(seed))
        assert fake[0] != "0"


def test_format_preserving_is_deterministic_for_a_given_rng_state() -> None:
    fake_a = pseudonyms.format_preserving("Kundennummer123", random.Random(7))
    fake_b = pseudonyms.format_preserving("Kundennummer123", random.Random(7))
    assert fake_a == fake_b


def test_compact_key_strips_all_whitespace() -> None:
    assert pseudonyms.compact_key("max mustermann") == "maxmustermann"
    assert pseudonyms.compact_key("DE89 3704 0044") == "DE8937040044"


def test_generate_iban_has_valid_checksum_and_keeps_country_code() -> None:
    original = "DE89370400440532013000"
    fake = pseudonyms.generate_iban(original, random.Random(3))
    assert len(fake) == len(original)
    assert fake[:2] == "DE"
    assert fake != original
    assert validate_iban(fake)


def test_generate_iban_keeps_an_x_mask_and_skips_checksum_recompute() -> None:
    masked = "DE893704XXXXXXXXXXXXXX"
    fake = pseudonyms.generate_iban(masked, random.Random(4))
    assert len(fake) == len(masked)
    for orig_ch, fake_ch in zip(masked, fake, strict=True):
        if orig_ch == "X":
            assert fake_ch == "X"
    assert fake[2:4] == masked[2:4]  # check digits left untouched when masked


def test_generate_dispatches_iban_through_the_checksum_path() -> None:
    fake = pseudonyms.generate("iban", "DE89370400440532013000", random.Random(5))
    assert validate_iban(fake)


def test_generate_strips_whitespace_before_generating() -> None:
    # A text-kind key keeps its internal spaces (needed by replace.py's word
    # matching); generation must still treat it as compact.
    fake = pseudonyms.generate("name", "max mustermann", random.Random(6))
    assert len(fake) == len("maxmustermann")
    assert " " not in fake
