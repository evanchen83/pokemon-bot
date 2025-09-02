#!/usr/bin/env bash
set -euo pipefail

# Load .env if it exists
if [ -f .env ]; then
  echo "Loading environment from .env file"
  export $(grep -v '^#' .env | xargs)
fi

# Validate required secrets
: "${POKEMON_TCG_API_KEY:?POKEMON_TCG_API_KEY is required for pokemon-bot}"

# Generic build function
build_image() {
  local service_name=$1
  local dockerfile_path=$2
  local image_tag=${3:-"${service_name}:latest"}

  echo "Building image: $image_tag using $dockerfile_path"

  docker build \
    -f "$dockerfile_path" \
    -t "$image_tag" \
    --build-arg POKEMON_TCG_API_KEY="$POKEMON_TCG_API_KEY" \
    --pull=False \
    .

  echo "Image built: $image_tag"
}

# build_image "pokemon-bot-base" "docker/bot-base/Dockerfile"
build_image "pokemon-bot" "docker/bot/Dockerfile"
