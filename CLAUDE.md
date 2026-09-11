# CLAUDE.md

## Project

Tool that drafts [invoice2data](https://github.com/invoice-x/invoice2data) templates with an LLM
**without sending personal data to the model**. Invoice text is pseudonymized first; the model only
ever sees fake values in the original format.

Workflow (the core contract, keep it intact):

1. **Extract text** from sample PDFs with the same invoice2data input backend the template will use.
2. **Find candidates** for personal data (names, addresses, IBANs, customer/account/contract numbers,
   phone numbers, mandate references, emails).
3. **Select** interactively which candidates to replace. Decisions are remembered.
4. **Persist pseudonyms** in a local store, generated once, reused on every run.
5. **Generate** a draft with invoice2data's AI template generator on the *replaced* text, drop anything
   that depends on a pseudonym, preview the draft against the *real* text, write YAML.

The starting point is the prototype `i2d_pseudonymize.py` and its test `test_i2d_pseudonymize.py`.
Refactor it into the package layout below; don't grow the single file further.

## Privacy rules (non-negotiable)

- Real invoice text must never reach a network AI provider. Only text that passed the leak check may
  be passed to `generate_template` / any `AIProvider`.
- **Fail closed**: if a selected value is still found after replacement (any spacing, line breaks,
  case-insensitive for text kinds), abort. Never "warn and continue".
- Never map pseudonyms back into a generated template. A keyword or regex containing a pseudonym is
  dropped, not repaired.
- Never print, log, or include in exceptions the contents of the pseudonym store or real invoice text
  beyond the local interactive prompt.
- Ask for confirmation before any call to a non-mock provider, unless `--defaults` is given.
- Never commit real invoices, extracted text, `.anon.txt` output, or pseudonym stores. Tests use
  synthetic invoices only. Don't read files under `samples/` into test fixtures.

## Layout (target)

```
src/i2d_pseudo/
  extract.py      text extraction via invoice2data.input (pdftotext CLI fallback)
  candidates.py   personal-data detection -> Candidate(kind, key, docs, context, ...)
  suggest.py      default yes/no per candidate (vendor context, varies across bills, ...)
  store.py        load/save pseudonym store (YAML, chmod 600), stable entry ids "kind:key"
  pseudonyms.py   format-preserving fake generation (valid IBAN check digits, keep spacing)
  replace.py      apply pseudonyms, keep pdftotext -layout column alignment, leak check
  generate.py     AI draft, pseudonym/real-text filtering, preview, YAML output
  cli.py          argparse entry point `i2d-pseudo`
tests/
  fixtures/       synthetic invoice texts only
samples/          local real PDFs (gitignored)
```

## Commands

```bash
uv sync --all-extras                 # install (invoice2data[ai], pytest, ruff, mypy)
uv run pytest                        # tests, must pass offline
uv run ruff check . && uv run ruff format .
uv run mypy src
uv run i2d-pseudo --no-ai samples/*.pdf        # stop after writing .anon.txt
uv run i2d-pseudo samples/*.pdf                # full workflow, asks before the AI call
```

`.gitignore` must contain: `samples/`, `*.anon.txt`, `pseudonyms*.yml`, `draft-template*.yml`, `.env`.

## invoice2data facts (verified against the docs for 1.0.1, recheck on upgrade)

- Text: `invoice2data.input.extract_text(module, path)`, backends in `invoice2data.input.INPUT_MODULES`.
  Default backend pdfium orders text differently from `pdftotext -layout` (it separated "Datum" from
  its date on the Telekom sample). Generate and test against one backend and pin it in the template
  with `input_module:`.
- AI config comes from `INVOICE2DATA_AI_PROVIDER` / `_MODEL` / `_BASE_URL` / `_API_KEY`.
  Default provider is `mock` (no network). Vendors: openai, deepseek, mistral, gemini, ollama.
- `AIProvider` is a structural protocol: `name`, `is_available()`,
  `extract_structured(text, json_schema, *, instructions=None)`.
- `generate_template(text, *, provider=None, issuer=None)` takes **one** sample text and grounds the
  model with candidate values from that text. Those values may end up in `instructions`, so both the
  text and the instructions must be clean.
- `TEMPLATE_SCHEMA`: the draft's `fields` map names to **plain regex strings** (no type/options).
- `preview_template(template, text)` returns the first capture per field; missing fields are omitted.
- `ai_fallback_extract(text, *, provider=None)` accepts a provider, but `extract_data(ai_fallback=True)`
  does not. `get_provider()` only returns mock or the OpenAI-compatible provider (no registry).
- Reusable helpers: `extract.validators.validate_iban` / `classify_identifier`,
  `extract.candidates.find_identifiers`. Prefer these over our own IBAN code.
- Canonical field names (`extract.schema.INVOICE_FIELDS`): use `amount`, `amount_untaxed`,
  `amount_tax`, `date`, `date_due`, `date_start`, `date_end`, `invoice_number`, `partner_ref`,
  `mandate_id`, `iban`. Note `vat` is the VAT **ID**, not the tax amount.
- Keywords are regexes; invalid regexes fall back to substring matching.

## Design decisions

- Pseudonyms are **format-preserving**: same length, digits for digits, letters kept, leading zeros
  kept, original spacing kept, valid IBAN mod-97 check digits (masked IBANs with `X` keep the mask).
  invoice2data only treats validated IBANs as candidates.
- One entry per normalized number regardless of which label it appeared under.
- Name entries also create `name_part` entries (≥3 chars, word-boundary matching) so "Herr Nachname"
  is covered. Titles (Herr/Frau/Dr.) are stripped before storing.
- Unlabeled numbers that differ between bills are per-invoice data (e.g. invoice number), not personal.
- Amounts and dates are not pseudonymized; changing them breaks net + tax = total consistency.
- A draft keyword/field is kept only if it matches **all real texts** and contains no pseudonym.

## Testing

- No network, no real invoices. Stub the AI API with a recording provider (see prototype test) and
  assert that no real value appears in anything the provider received, including `instructions`.
- Every detector gets a synthetic fixture with a positive and a vendor/negative case.
- Replacement tests: spacing variants (`562 746 4667` vs `5627464667`), values split across lines,
  column alignment preserved, rerun with an existing store is byte-identical.
- When changing detection heuristics, keep the vendor cases (vendor IBAN in footer, service numbers
  like 0800…, USt-IdNr., Gläubiger-ID) suggested as "keep".

## Backlog

1. Verify the AI step against real invoice2data (so far only stubs of the documented API). Check how
   `generate_template` builds its prompt.
2. Use several samples: generate from one, validate on the rest; later merge drafts.
3. Post-process drafts: add `type`, `decimal_separator`, `date_formats`, `group: first` automatically.
4. Detection gaps: labels above values beyond the next line, non-German labels, names outside
   salutation/address block, contract addresses that differ from the billing address.
5. Pull request to invoice2data: wrap the provider in `get_provider()` when e.g.
   `INVOICE2DATA_AI_PII_FILE` is set, so `invoice2data --new-template` can use the store.

Out of scope for now: Paperless-ngx integration (planned later as a separate webhook service).

## Conventions

- Python ≥ 3.10, type hints everywhere, `from __future__ import annotations`.
- Keep modules free of I/O except `extract.py`, `store.py`, `cli.py`; everything else is pure and
  unit-testable with strings.
- User-facing messages in English; label dictionaries may be multilingual.
