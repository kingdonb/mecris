# HCAT Sandbox — Hardened Container for Autonomous Turns
# Alpine 3.21 pinned by SHA256 digest (amd64, fetched 2026-04-24).
# To refresh the digest: docker pull alpine:3.21 && docker inspect --format='{{index .RepoDigests 0}}' alpine:3.21
FROM alpine@sha256:48b0309ca019d89d40f670aa1bc06e426dc0931948452e8491e3d65087abc07d

# Install only the dependencies needed for autonomous agent turns.
# py3-pip is NOT installed — uv manages all Python package installation.
RUN apk add --no-cache \
    python3 \
    git \
    curl \
    ca-certificates \
    bash

# Install uv to a system-wide location so it is available to all users.
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a non-root user. All agent code runs as this user.
RUN addgroup -S mecris && adduser -S mecris -G mecris

# Working directory for the agent workspace (mounted at runtime).
WORKDIR /workspace
RUN chown mecris:mecris /workspace

# Drop privileges.
USER mecris

# Smoke-test: ensure all required tools are present at image build time.
RUN python3 --version && git --version && uv --version

# Default shell — the actual entrypoint is provided at `docker run` time.
CMD ["bash"]

# NETWORK ISOLATION NOTE:
# LAN isolation is enforced at RUNTIME, not in this file.
# Run with: --network=host is FORBIDDEN. Use:
#   docker run --network=mecris-egress-only <image>
# where mecris-egress-only is a custom bridge network without local routing.
# See scripts/build_hcat.sh for the full invocation pattern.
