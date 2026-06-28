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
BUILDX ?= docker buildx build --load

.PHONY: images base api worker

# Build every service image (base first).
images: base api worker

base:
	$(BUILDX) -f docker/base.Dockerfile -t $(BASE_IMAGE) .

api: base
	$(BUILDX) -f services/api/Dockerfile \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) \
		-t rs-recruiting-api:$(IMAGE_TAG) .

worker: base
	$(BUILDX) -f services/worker/Dockerfile \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) \
		-t rs-recruiting-worker:$(IMAGE_TAG) .
