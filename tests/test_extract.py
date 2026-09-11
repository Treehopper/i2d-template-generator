from __future__ import annotations

from pathlib import Path

import pytest

from i2d_pseudo import extract


def test_extract_text_via_text_backend(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("hello invoice", encoding="utf-8")
    assert extract.extract_text(sample, backend="text") == "hello invoice"


def test_unknown_backend_raises_value_error(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        extract.extract_text(sample, backend="nope")


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract.extract_text(tmp_path / "missing.pdf")


def test_falls_back_to_pdftotext_cli_when_backend_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-fake")

    monkeypatch.setattr(extract, "is_available", lambda module: False)
    monkeypatch.setattr(extract.shutil, "which", lambda name: "/usr/bin/pdftotext")

    class FakeCompleted:
        stdout = b"fallback text"

    def fake_run(cmd: list[str], capture_output: bool, check: bool) -> FakeCompleted:
        assert cmd[0] == "pdftotext"
        return FakeCompleted()

    monkeypatch.setattr(extract.subprocess, "run", fake_run)
    assert extract.extract_text(pdf, backend="pdftotext") == "fallback text"


def test_raises_oserror_when_neither_backend_nor_cli_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-fake")

    monkeypatch.setattr(extract, "is_available", lambda module: False)
    monkeypatch.setattr(extract.shutil, "which", lambda name: None)

    with pytest.raises(OSError):
        extract.extract_text(pdf, backend="pdftotext")
