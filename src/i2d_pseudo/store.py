"""Persistent pseudonym store.

YAML file keyed by stable entry id ``"kind:key"``, written with ``chmod 600``
since it holds real personal data (the store's whole point is to remember it
locally so it is never re-derived from -- or re-shown alongside -- the
invoice text on a later run). The only I/O in this module is load/save.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class StoreEntry:
    """One remembered decision for a candidate.

    Attributes:
        kind (str): Candidate kind, e.g. "iban", "name".
        key (str): The normalized original value (sensitive -- never log this).
        decision (str): "replace" or "keep".
        pseudonym (str | None): The generated fake value (compact, no
            whitespace) when ``decision == "replace"``; None for "keep".
    """

    kind: str
    key: str
    decision: str
    pseudonym: str | None = None


def entry_id(kind: str, key: str) -> str:
    """Build the stable store id for a candidate.

    Args:
        kind (str): Candidate kind.
        key (str): Normalized candidate key.

    Returns:
        str: The id, ``"kind:key"``.
    """
    return f"{kind}:{key}"


def load_store(path: Path) -> dict[str, StoreEntry]:
    """Load a pseudonym store from disk.

    Args:
        path (Path): Store file path. Missing file yields an empty store.

    Returns:
        dict[str, StoreEntry]: Entry id -> entry.
    """
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        eid: StoreEntry(
            kind=fields["kind"],
            key=fields["key"],
            decision=fields["decision"],
            pseudonym=fields.get("pseudonym"),
        )
        for eid, fields in raw.items()
    }


def save_store(path: Path, store: Mapping[str, StoreEntry]) -> None:
    """Save a pseudonym store to disk, restricting its permissions to 600.

    Args:
        path (Path): Store file path.
        store (Mapping[str, StoreEntry]): Entry id -> entry.
    """
    data = {
        eid: {
            "kind": entry.kind,
            "key": entry.key,
            "decision": entry.decision,
            **({"pseudonym": entry.pseudonym} if entry.pseudonym is not None else {}),
        }
        for eid, entry in store.items()
    }
    content = yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    path.chmod(0o600)
