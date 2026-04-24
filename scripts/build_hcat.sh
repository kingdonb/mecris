#!/usr/bin/env bash
# build_hcat.sh — Build and verify the HCAT sandbox image.
# Usage: bash scripts/build_hcat.sh
# See: kingdonb/mecris#210, yebyen/mecris#265
set -euo pipefail

DOCKERFILE="docker/hcat.Dockerfile"
IMAGE_NAME="mecris-hcat"
IMAGE_TAG="latest"

cd "$(git rev-parse --show-toplevel)"

echo "==> Building HCAT sandbox image..."
docker build \
    --file "${DOCKERFILE}" \
    --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
    --progress=plain \
    .

echo ""
echo "==> Image built. Verifying digest..."
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_NAME}:${IMAGE_TAG}" 2>/dev/null || echo "(local image, no registry digest yet)")
echo "    Digest: ${DIGEST}"

echo ""
echo "==> Smoke-testing tool availability inside container..."
docker run --rm --network=none "${IMAGE_NAME}:${IMAGE_TAG}" bash -c "
    echo '--- python3'; python3 --version
    echo '--- git';     git --version
    echo '--- uv';      uv --version
    echo '--- whoami';  whoami
"

echo ""
echo "==> HCAT sandbox image is ready: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Runtime invocation pattern (network-isolated):"
echo "  docker network create --driver bridge --internal mecris-egress-only 2>/dev/null || true"
echo "  docker run --rm \\"
echo "    --network=mecris-egress-only \\"
echo "    --user=mecris \\"
echo "    --read-only \\"
echo "    --tmpfs /tmp:rw,noexec,nosuid,size=128m \\"
echo "    --mount type=bind,src=\$(pwd),dst=/workspace,readonly \\"
echo "    ${IMAGE_NAME}:${IMAGE_TAG} \\"
echo "    bash -c '<agent command>'"
