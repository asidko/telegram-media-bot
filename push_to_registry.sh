#!/bin/bash

# This script will build a new image and push the updates to docker registry

# Get the current git tag
TAG=$(git describe --tags --abbrev=0)
echo "Going to push the image with tag: $TAG"
# Exit if no tag is found
if [ -z "$TAG" ]; then
  echo "No tag found. Exiting"
  exit 1
fi

# Build the image
IMAGE=windranger/telegram-media-bot:$TAG
echo "Building the image $IMAGE"
docker build -t $IMAGE .
# Assign latest tag to the image
docker tag $IMAGE windranger/telegram-media-bot:latest

# Login to docker registry
echo "Logging in to docker registry"
# Read password and username from environment variables .env file
export $(grep -v '^#' .env | xargs)
echo $DOCKER_PASSWORD | docker login -u windranger --password-stdin

# Push the image to docker registry
echo "Pushing the image to docker registry"
docker push $IMAGE
docker push windranger/telegram-media-bot:latest
