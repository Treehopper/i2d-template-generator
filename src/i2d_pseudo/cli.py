"""``i2d-pseudo`` command-line entry point.

Orchestrates the full workflow: extract -> find candidates -> select
interactively (remembering decisions in the store) -> persist pseudonyms ->
replace -> (unless ``--no-ai``) draft a template with the AI provider ->
filter -> preview -> write YAML.

The only I/O outside `extract.py` and `store.py` lives here: reading PDFs,
prompting the user, and writing the ``.anon.txt`` / draft-template files.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from invoice2data.ai import AIProvider, get_provider

from . import candidates as candidates_mod
from . import extract as extract_mod
from . import generate as generate_mod
from . import pseudonyms as pseudonyms_mod
from . import replace as replace_mod
from . import store as store_mod
from . import suggest as suggest_mod
from .store import StoreEntry

AskFn = Callable[[str, bool], bool]


def _ask_stdin(prompt: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False


def build_parser() -> argparse.ArgumentParser:
    """Build the ``i2d-pseudo`` argument parser.

    Returns:
        argparse.ArgumentParser: The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="i2d-pseudo",
        description=(
            "Draft an invoice2data template from sample PDFs, pseudonymizing "
            "personal data before any of it reaches an AI provider."
        ),
    )
    parser.add_argument("pdfs", nargs="+", type=Path, help="sample invoice PDFs")
    parser.add_argument(
        "--backend",
        default=extract_mod.DEFAULT_BACKEND,
        help=f"invoice2data input backend to pin (default: {extract_mod.DEFAULT_BACKEND})",
    )
    parser.add_argument(
        "--store", type=Path, default=Path("pseudonyms.yml"), help="pseudonym store file"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("draft-template.yml"), help="draft template output file"
    )
    parser.add_argument(
        "--no-ai", action="store_true", help="stop after writing .anon.txt, skip the AI draft"
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="accept every suggested keep/replace decision and skip the AI-call confirmation",
    )
    return parser


def run(
    pdf_paths: Sequence[Path],
    *,
    backend: str,
    store_path: Path,
    out_path: Path,
    no_ai: bool,
    use_defaults: bool,
    ask: AskFn = _ask_stdin,
    rng: random.Random | None = None,
    provider: AIProvider | None = None,
    stdout: TextIO = sys.stdout,
) -> None:
    """Run the full pseudonymize-and-draft workflow.

    Args:
        pdf_paths (Sequence[Path]): Sample invoice PDFs.
        backend (str): invoice2data input backend to pin.
        store_path (Path): Pseudonym store file.
        out_path (Path): Draft template output file.
        no_ai (bool): Stop after writing ``.anon.txt``.
        use_defaults (bool): Accept every suggested decision and skip the
            AI-call confirmation.
        ask (AskFn): Prompt function ``(prompt, default) -> bool``; overridable
            for tests.
        rng (random.Random | None): Randomness source for pseudonym
            generation; a fresh one when None.
        provider (AIProvider | None): AI provider to use; the configured one
            (env-resolved) when None.
        stdout (TextIO): Where to print progress; overridable for tests.
    """
    rng = rng or random.Random()
    documents = {str(p): extract_mod.extract_text(p, backend=backend) for p in pdf_paths}

    store = store_mod.load_store(store_path)
    for candidate in candidates_mod.find_candidates(documents):
        eid = store_mod.entry_id(candidate.kind, candidate.key)
        if eid in store:
            continue
        default = suggest_mod.suggest(candidate)
        if use_defaults:
            replace = default
        else:
            prompt = f"[{candidate.kind}] {candidate.context!r} -- replace with a pseudonym?"
            replace = ask(prompt, default)
        pseudonym = pseudonyms_mod.generate(candidate.kind, candidate.key, rng) if replace else None
        store[eid] = StoreEntry(
            kind=candidate.kind,
            key=candidate.key,
            decision="replace" if replace else "keep",
            pseudonym=pseudonym,
        )
    store_mod.save_store(store_path, store)

    entries = list(store.values())
    safe_texts: dict[str, replace_mod.SafeText] = {}
    for doc_path, text in documents.items():
        safe = replace_mod.replace_document(text, entries)
        safe_texts[doc_path] = safe
        anon_path = Path(doc_path).with_suffix(".anon.txt")
        anon_path.write_text(safe.text, encoding="utf-8")
        print(f"wrote {anon_path}", file=stdout)

    if no_ai:
        return

    provider = provider or get_provider()
    if not use_defaults and provider.name != "mock":
        proceed = ask(
            f"About to call the '{provider.name}' AI provider with pseudonymized "
            "text only. Continue?",
            True,
        )
        if not proceed:
            print("aborted before AI call", file=stdout)
            return

    first_doc = str(pdf_paths[0])
    draft = generate_mod.draft_template(safe_texts[first_doc], provider=provider)
    draft = generate_mod.drop_pseudonym_dependent(draft, store)
    draft = generate_mod.keep_matching_all(draft, documents.values())

    preview = generate_mod.preview(draft, documents[first_doc])
    print("preview (captured from your real sample text):", file=stdout)
    for field, value in preview.items():
        print(f"  {field}: {value}", file=stdout)

    out_path.write_text(generate_mod.render_yaml(draft), encoding="utf-8")
    print(f"wrote {out_path}", file=stdout)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv (list[str] | None): Arguments to parse; ``sys.argv[1:]`` when None.

    Returns:
        int: Process exit code.
    """
    args = build_parser().parse_args(argv)
    run(
        args.pdfs,
        backend=args.backend,
        store_path=args.store,
        out_path=args.out,
        no_ai=args.no_ai,
        use_defaults=args.defaults,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
