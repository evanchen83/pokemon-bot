# Dockerfile.bot-base

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && apt-get clean

# Install minimal dependency for fetching cards
RUN pip install --no-cache-dir requests

# Add fetch script
COPY docker/bot-base/scripts/fetch_cards.py ./fetch_cards.py

# Pass in API key via build arg/env
ARG POKEMON_TCG_API_KEY
ENV POKEMON_TCG_API_KEY=$POKEMON_TCG_API_KEY

# Run fetch during build
RUN python -u fetch_cards.py