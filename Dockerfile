# Build the Node demo resolver's dependencies in a Node image.
FROM node:22-slim AS resolver
WORKDIR /resolver
COPY resolver/package.json resolver/package-lock.json ./
RUN npm ci --omit=dev
COPY resolver/resolve.js ./

FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /uvx /bin/
# The Node runtime, to run the demo resolver (its deps come from the stage above).
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

RUN /app/.venv/bin/awpy get tris

COPY --from=resolver /resolver ./resolver
COPY bot/ ./bot/

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "bot.main"]
