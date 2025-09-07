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

  docker buildx build \
    --platform=linux/amd64 \
    -f "$dockerfile_path" \
    -t "$image_tag" \
    --build-arg POKEMON_TCG_API_KEY="$POKEMON_TCG_API_KEY" \
    --pull=false \
    --load \
    .


  echo "Image built: $image_tag"
}

# Build all images
build_image "pokemon-bot-base" "docker/bot-base/Dockerfile" 
build_image "pokemon-bot" "docker/bot/Dockerfile"
build_image "card-db-init" "docker/card-db-init/Dockerfile"
