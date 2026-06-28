# Container builds for the RS Recruitment services.
#
# Uses Docker Buildx (BuildKit). The service Dockerfiles use a uv cache mount
# (RUN --mount=type=cache) so dependency wheels are reused across builds without
# bloating the images — this REQUIRES BuildKit/buildx (the legacy builder errors
# on --mount). Install locally with `docker buildx install` or the buildx plugin;
# in CI use docker/setup-buildx-action.
#
# The base image must be built first; the api and worker images build FROM it.
# Build context is always the repo root (the service Dockerfiles reach into
# libs/shared and the workspace manifests).

IMAGE_TAG ?= local
BASE_IMAGE ?= rs-recruiting-base:$(IMAGE_TAG)
BUILD ?= docker buildx build --load

.PHONY: images base api worker up down logs

# Build every service image (base first).
images: base api worker

# Bring up the full local stack (builds images first, since compose does not
# build the shared base image).
up: images
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api worker

base:
	$(BUILD) -f docker/base.Dockerfile -t $(BASE_IMAGE) .

api: base
	$(BUILD) -f services/api/Dockerfile \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) \
		-t rs-recruiting-api:$(IMAGE_TAG) .

worker: base
	$(BUILD) -f services/worker/Dockerfile \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) \
		-t rs-recruiting-worker:$(IMAGE_TAG) .
