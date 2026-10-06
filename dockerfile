FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_NO_DEV=1 \
    UV_PYTHON_INSTALL_DIR=/python

RUN uv python install 3.13;

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project;

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen;


FROM debian:trixie-slim

WORKDIR /app

COPY --from=builder  /python /python
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

RUN chmod +x /app/entrypoint.sh
