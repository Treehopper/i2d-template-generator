from __future__ import annotations

import stat
from pathlib import Path

from i2d_pseudo import store


def test_entry_id_format() -> None:
    assert store.entry_id("iban", "DE1") == "iban:DE1"


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "pseudonyms.yml"
    entries = {
        store.entry_id("iban", "DE1"): store.StoreEntry(
            kind="iban", key="DE1", decision="replace", pseudonym="XX2"
        ),
        store.entry_id("phone", "0800"): store.StoreEntry(
            kind="phone", key="0800", decision="keep", pseudonym=None
        ),
    }
    store.save_store(path, entries)
    assert store.load_store(path) == entries


def test_missing_file_yields_empty_store(tmp_path: Path) -> None:
    assert store.load_store(tmp_path / "does-not-exist.yml") == {}


def test_saved_file_is_chmod_600(tmp_path: Path) -> None:
    path = tmp_path / "pseudonyms.yml"
    store.save_store(path, {})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_resaving_an_existing_looser_permission_file_tightens_it(tmp_path: Path) -> None:
    path = tmp_path / "pseudonyms.yml"
    path.write_text("{}\n", encoding="utf-8")
    path.chmod(0o644)
    store.save_store(path, {})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_rerun_with_same_store_is_byte_identical_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "pseudonyms.yml"
    entries = {
        store.entry_id("name", "max"): store.StoreEntry(
            kind="name", key="max", decision="replace", pseudonym="xyz"
        )
    }
    store.save_store(path, entries)
    first = path.read_bytes()
    store.save_store(path, store.load_store(path))
    assert path.read_bytes() == first
