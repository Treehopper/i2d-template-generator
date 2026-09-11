"""Text extraction via invoice2data's input backends, with a pdftotext CLI fallback.

The backend is pinned (default ``pdftotext``) rather than left to invoice2data's
own default (``pdfium``), since different backends order text differently --
the template must be generated and tested against the same backend it will run
with, and the generated template records ``input_module:`` to pin it there too.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from invoice2data.input import INPUT_MODULES, is_available
from invoice2data.input import extract_text as _i2d_extract_text

DEFAULT_BACKEND = "pdftotext"


def extract_text(path: Path | str, *, backend: str = DEFAULT_BACKEND) -> str:
    """Extract text from a PDF with a pinned invoice2data input backend.

    Args:
        path (Path | str): PDF file path.
        backend (str): invoice2data input backend name (a key of
            ``invoice2data.input.INPUT_MODULES``).

    Returns:
        str: The extracted text.

    Raises:
        ValueError: ``backend`` is not a known invoice2data input backend.
        FileNotFoundError: ``path`` does not exist.
        OSError: The backend's dependency is unavailable and no ``pdftotext``
            CLI fallback is on PATH either.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    module = INPUT_MODULES.get(backend)
    if module is None:
        raise ValueError(f"unknown input backend: {backend!r}")
    if is_available(module):
        return _i2d_extract_text(module, str(path))
    if shutil.which("pdftotext") is None:
        raise OSError(
            f"input backend {backend!r} is unavailable and no pdftotext CLI "
            "fallback was found on PATH"
        )
    proc = subprocess.run(
        ["pdftotext", "-layout", "-q", "-enc", "UTF-8", str(path), "-"],
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode("utf-8")
