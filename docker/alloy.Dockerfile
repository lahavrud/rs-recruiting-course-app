# Grafana Alloy with the rs-recruiting observability pipeline baked in.
#
# The public grafana/alloy image ships no config, and Fargate has no easy way to
# mount one, so the config is built into the image. CI pushes this to the Ops
# ECR repo rs-recruiting/alloy; the tofu ecs-service module runs it as the OTLP
# sidecar in every ECS task (api + worker).
#
# Build from the repo root:
#   docker build -f docker/alloy.Dockerfile -t rs-recruiting-alloy:local .
#
# Runtime config (env vars) is injected by the task definition — see the header
# of alloy/config.alloy. The default grafana/alloy entrypoint runs
# `/etc/alloy/config.alloy`.

FROM grafana/alloy:v1.17.0

COPY alloy/config.alloy /etc/alloy/config.alloy
