from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from i2d_pseudo import cli
from i2d_pseudo import store as store_mod


class RecordingProvider:
    def __init__(self, response: dict[str, Any], name: str = "mock") -> None:
        self._response = response
        self.name = name
        self.calls: list[str] = []

    def is_available(self) -> bool:
        return True

    def extract_structured(
        self, text: str, json_schema: dict[str, Any], *, instructions: str | None = None
    ) -> dict[str, Any]:
        self.calls.append(text)
        return dict(self._response)


PERSONAL_TEXT = "Herr\nMax Mustermann\n\nKundennummer: 123456789\n"


def _patch_extract(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(cli.extract_mod, "extract_text", lambda path, backend: text)


def test_no_ai_writes_anon_txt_without_leaking_real_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "sample.pdf"
    doc.write_bytes(b"fake")
    _patch_extract(monkeypatch, PERSONAL_TEXT)

    cli.run(
        [doc],
        backend="text",
        store_path=tmp_path / "pseudonyms.yml",
        out_path=tmp_path / "draft-template.yml",
        no_ai=True,
        use_defaults=True,
    )

    anon_path = doc.with_suffix(".anon.txt")
    assert anon_path.exists()
    anon_text = anon_path.read_text(encoding="utf-8")
    assert "Max Mustermann" not in anon_text
    assert "123456789" not in anon_text


def test_decisions_are_remembered_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "sample.pdf"
    doc.write_bytes(b"fake")
    _patch_extract(monkeypatch, PERSONAL_TEXT)
    store_path = tmp_path / "pseudonyms.yml"

    cli.run(
        [doc],
        backend="text",
        store_path=store_path,
        out_path=tmp_path / "draft-template.yml",
        no_ai=True,
        use_defaults=True,
    )
    saved = store_mod.load_store(store_path)
    assert len(saved) > 0

    def _fail_if_asked(prompt: str, default: bool) -> bool:
        raise AssertionError("should not re-prompt for a remembered decision")

    cli.run(
        [doc],
        backend="text",
        store_path=store_path,
        out_path=tmp_path / "draft-template.yml",
        no_ai=True,
        use_defaults=False,
        ask=_fail_if_asked,
    )
    assert store_mod.load_store(store_path) == saved


def test_full_ai_flow_with_mock_provider_writes_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "Fake Corp\nHerr\nMax Mustermann\n\nGesamtbetrag: 12,34 EUR\n"
    doc = tmp_path / "sample.pdf"
    doc.write_bytes(b"fake")
    _patch_extract(monkeypatch, text)

    provider = RecordingProvider(
        {
            "issuer": "Fake Corp",
            "keywords": ["Fake Corp"],
            "fields": {"amount": r"Gesamtbetrag:\s+([\d,]+)\s+EUR"},
        }
    )
    out_path = tmp_path / "draft-template.yml"

    cli.run(
        [doc],
        backend="text",
        store_path=tmp_path / "pseudonyms.yml",
        out_path=out_path,
        no_ai=False,
        use_defaults=True,
        provider=provider,
    )

    assert out_path.exists()
    assert "Max Mustermann" not in provider.calls[0]
    rendered = out_path.read_text(encoding="utf-8")
    assert "amount" in rendered


def test_non_mock_provider_requires_confirmation_and_is_skipped_on_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "Fake Corp\nGesamtbetrag: 1,00 EUR\n"
    doc = tmp_path / "sample.pdf"
    doc.write_bytes(b"fake")
    _patch_extract(monkeypatch, text)

    provider = RecordingProvider({"keywords": [], "fields": {}}, name="openai")
    out_path = tmp_path / "draft-template.yml"
    prompts: list[str] = []

    def _deny(prompt: str, default: bool) -> bool:
        prompts.append(prompt)
        return False

    cli.run(
        [doc],
        backend="text",
        store_path=tmp_path / "pseudonyms.yml",
        out_path=out_path,
        no_ai=False,
        use_defaults=False,
        ask=_deny,
        provider=provider,
    )

    assert prompts
    assert not out_path.exists()
    assert provider.calls == []


def test_defaults_flag_skips_the_ai_call_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "Fake Corp\nGesamtbetrag: 1,00 EUR\n"
    doc = tmp_path / "sample.pdf"
    doc.write_bytes(b"fake")
    _patch_extract(monkeypatch, text)

    provider = RecordingProvider(
        {"issuer": "Fake Corp", "keywords": ["Fake Corp"], "fields": {}}, name="openai"
    )

    def _fail_if_asked(prompt: str, default: bool) -> bool:
        raise AssertionError("--defaults must skip the AI-call confirmation")

    cli.run(
        [doc],
        backend="text",
        store_path=tmp_path / "pseudonyms.yml",
        out_path=tmp_path / "draft-template.yml",
        no_ai=False,
        use_defaults=True,
        ask=_fail_if_asked,
        provider=provider,
    )
    assert provider.calls  # the call went through without confirmation
