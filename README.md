# i2d-template-generator

Drafts [invoice2data](https://github.com/invoice-x/invoice2data) templates with an LLM
**without sending personal data to the model**. Invoice text is pseudonymized locally first;
the model only ever sees fake values in the original format. See [CLAUDE.md](CLAUDE.md) for
the full design and privacy contract.

## Workflow

Reach for an AI model only when invoice2data's own deterministic template drafting isn't good
enough — it's the last step, not the first:

1. **Draft a template with invoice2data's built-in heuristics.** Deterministic, offline, no AI
   involved at all — `invoice2data --new-template`.
2. **Extract with that template** and check whether the captured fields look right —
   `invoice2data --template-folder`.
3. **Not satisfied?** *Now* draft a template with an AI model — via `i2d-pseudo` (this repo's
   tool), which pseudonymizes the invoice text first so nothing personal ever reaches the
   model. (Never invoice2data's own `--ai`/`--ai-fallback` flags on a real invoice — those send
   the real text to the configured provider.)
4. **Extract with the final template** — same command as step 2, now pointed at whichever
   template (heuristic or AI-drafted) you decided to keep.

Steps 1, 2, and 4 are plain `invoice2data`, already installed alongside `i2d-pseudo` (it's a
dependency of this project) — see below for exact commands, both locally and via the Docker
image, which bundles both CLIs.

## Usage via the Docker image

The published image bundles `invoice2data`, poppler's `pdftotext` (the default text-extraction
backend), and the `i2d-pseudo` CLI. `i2d-pseudo` is the default entrypoint (step 3, below);
override it with `--entrypoint invoice2data` for steps 1, 2, and 4.

### Pull

```bash
docker pull ghcr.io/treehopper/i2d-template-generator:latest
```

Images are multi-arch (`linux/amd64` and `linux/arm64`, e.g. Apple Silicon), and are also
tagged by branch (`:develop`), by short commit SHA (`:sha-xxxxxxx`), and by version for tagged
releases (`:1.2.3`, `:1.2`). If `docker pull` reports "unauthorized" or "not found", the
package on GHCR may still be private — either `docker login ghcr.io` with a token that has
read access, or make the package public from the repository's **Packages** tab.

Alternatively, build it yourself from a checkout of this repo:

```bash
docker build -t i2d-pseudo .
```

All the commands below mount the directory holding your sample invoices (and where templates,
the pseudonym store, and output land) at `/data` — nothing else is writable, and nothing from
`/data` is ever baked into the image. Run them from inside that directory so filenames line up
on both sides of the mount. Locally (no Docker), drop the `docker run ...` wrapper and run the
same flags with `uv run invoice2data ...` / `uv run i2d-pseudo ...` instead.

### 1. Draft a template with invoice2data's heuristics

```bash
cd path/to/your/samples
mkdir -p templates
docker run --rm -it -v "$PWD":/data --entrypoint invoice2data \
  ghcr.io/treehopper/i2d-template-generator:latest \
  --new-template invoice.pdf --template-out templates/vendor.yml
```

This is deterministic and fully offline (no AI, no network) — it prints the drafted template
and a preview of what each field captures, then asks before writing `templates/vendor.yml`.
Add `--interactive` to review/edit/drop each field, or `-i pdftotext` to pin the input backend
(recommended — see [CLAUDE.md](CLAUDE.md)'s invoice2data notes on why).

### 2. Extract with the drafted template

```bash
docker run --rm -v "$PWD":/data --entrypoint invoice2data \
  ghcr.io/treehopper/i2d-template-generator:latest \
  --template-folder templates --exclude-built-in-templates \
  -f json -o extracted invoice.pdf
cat extracted.json
```

`--exclude-built-in-templates` keeps the match to just your own drafted templates, so you're
only looking at what step 1 produced. Drop it once you're done comparing.

### 3. Not satisfied? Draft a template with AI instead

```bash
docker run --rm -it -v "$PWD":/data ghcr.io/treehopper/i2d-template-generator:latest *.pdf
```

This extracts text, finds personal-data candidates, and prompts you interactively to
replace/keep each one (`-it` is required for the prompts) before asking to confirm the AI
call. `pseudonyms.yml`, `*.anon.txt`, and `draft-template.yml` are written back into `/data`
too, owned by the container's `i2d` user (uid 1000) — add `--user "$(id -u):$(id -g)"` to the
`docker run` command if you'd rather they were owned by your host user. Once you're happy with
`draft-template.yml`'s preview, copy or rename it into `templates/` for step 4.

Useful flags (see `docker run --rm ghcr.io/treehopper/i2d-template-generator:latest --help`):

```bash
# Stop after pseudonymizing, before any AI call — inspect *.anon.txt yourself first.
docker run --rm -it -v "$PWD":/data ghcr.io/treehopper/i2d-template-generator:latest \
  --no-ai *.pdf

# Non-interactive: accept every suggested keep/replace decision and skip the AI-call
# confirmation (decisions already in pseudonyms.yml from a prior run are always reused).
docker run --rm -v "$PWD":/data ghcr.io/treehopper/i2d-template-generator:latest \
  --defaults *.pdf

# Custom store/output locations, and pinning a non-default input backend.
docker run --rm -it -v "$PWD":/data ghcr.io/treehopper/i2d-template-generator:latest \
  --store my-pseudonyms.yml --out my-draft-template.yml --backend pdfium *.pdf
```

By default the AI provider is `mock` (no network call at all). To use a real provider, pass
its configuration as environment variables — the API key never needs to be baked into the
image or the repo:

```bash
docker run --rm -it -v "$PWD":/data \
  -e INVOICE2DATA_AI_PROVIDER=openai \
  -e INVOICE2DATA_AI_MODEL=gpt-4o-mini \
  -e INVOICE2DATA_AI_API_KEY="$OPENAI_API_KEY" \
  ghcr.io/treehopper/i2d-template-generator:latest *.pdf
```

Only pseudonymized text (verified leak-free) is ever sent to a configured provider — see
[CLAUDE.md](CLAUDE.md)'s privacy rules for the full guarantee.

### 4. Extract with the final template

Same command as step 2, once you've copied whichever template you're keeping (heuristic or
AI-drafted) into `templates/`:

```bash
docker run --rm -v "$PWD":/data --entrypoint invoice2data \
  ghcr.io/treehopper/i2d-template-generator:latest \
  --template-folder templates --exclude-built-in-templates \
  -f json -o extracted invoice.pdf
cat extracted.json
```

Drop `--exclude-built-in-templates` in normal use once the template is finished, so
invoice2data's built-in templates are also available as a fallback for other vendors.
