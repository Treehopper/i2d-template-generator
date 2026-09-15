# syntax=docker/dockerfile:1

# Build the virtualenv separately so dependency layers are cached independently
# of source changes (the lockfile only changes when a dependency changes).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

# invoice2data's default input backend (pdftotext, see extract.py) needs
# poppler's pdftotext CLI; nothing else in this image runs as root at runtime.
FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin i2d

COPY --from=builder --chown=i2d:i2d /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Samples, the pseudonym store, and draft templates are expected to live on a
# mounted volume -- never baked into the image (see CLAUDE.md's privacy rules
# and .gitignore). I2D_DATA_DIR/--data-dir can point elsewhere at runtime;
# this just matches the CLI's own default so a bare `docker run` (no extra
# args, no flags) already works against whatever is mounted at /data.
ENV I2D_DATA_DIR=/data
WORKDIR /data
USER i2d

ENTRYPOINT ["i2d-pseudo"]
