FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

RUN /app/.venv/bin/awpy get tris

COPY bot/ ./bot/

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "bot.main"]
