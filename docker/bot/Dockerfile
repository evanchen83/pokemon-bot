# Dockerfile

FROM pokemon-bot-base:latest as base

FROM python:3.11-slim

WORKDIR /app

# Install dependencies for Poetry & build tools
RUN apt-get update && apt-get install -y curl git build-essential && apt-get clean

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.8.2 python3 -
ENV PATH="/root/.local/bin:$PATH"
ENV POETRY_VIRTUALENVS_CREATE=false

# Copy only dependency files and install first (to cache)
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY bot ./bot
COPY --from=base /app/data /app/data

CMD ["python", "-m", "bot.bot"]