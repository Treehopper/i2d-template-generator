# i2d-template-generator

Drafts [invoice2data](https://github.com/invoice-x/invoice2data) templates with an LLM
**without sending personal data to the model**. Invoice text is pseudonymized locally first;
the model only ever sees fake values in the original format. See [CLAUDE.md](CLAUDE.md) for
the full design and privacy contract.

## Usage via the Docker image

The published image bundles `invoice2data`, poppler's `pdftotext` (the default text-extraction
backend), and the `i2d-pseudo` CLI as its entrypoint.

### Pull

```bash
docker pull ghcr.io/treehopper/i2d-template-generator:latest
```

Images are also tagged by branch (`:develop`), by short commit SHA (`:sha-xxxxxxx`), and by
version for tagged releases (`:1.2.3`, `:1.2`). If `docker pull` reports "unauthorized" or
"not found", the package on GHCR may still be private — either `docker login ghcr.io` with a
token that has read access, or make the package public from the repository's **Packages** tab.

Alternatively, build it yourself from a checkout of this repo:

```bash
docker build -t i2d-pseudo .
```

### Run

Sample PDFs, the pseudonym store, and the generated draft template all live under `/data` in
the container — nothing else is writable, and nothing from `/data` is ever baked into the
image. Mount the directory that holds your sample invoices there, then run from inside it so
filenames line up on both sides of the mount:

```bash
cd path/to/your/samples
docker run --rm -it -v "$PWD":/data ghcr.io/treehopper/i2d-template-generator:latest *.pdf
```

This extracts text, finds personal-data candidates, and prompts you interactively to
replace/keep each one (`-it` is required for the prompts) before asking to confirm the AI
call. `pseudonyms.yml`, `*.anon.txt`, and `draft-template.yml` are written back into the
mounted directory, owned by the container's `i2d` user (uid 1000) — add
`--user "$(id -u):$(id -g)"` to the `docker run` command if you'd rather they were owned by
your host user.

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
