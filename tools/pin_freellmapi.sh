#!/usr/bin/env bash
# Resolve a FreeLLMAPI release tag to its immutable digest, smoke-test that exact image, and write freellmapi.lock.
#   bash tools/pin_freellmapi.sh v0.12.0
# Used by .github/workflows/pin-freellmapi.yml (it opens a PR with the change). Never trusts a tag it has not pulled.
set -euo pipefail
TAG="${1:?usage: pin_freellmapi.sh <tag, e.g. v0.12.0>}"
case "$TAG" in latest|main|sha-*) echo "::error::pin a release tag (vX.Y.Z), not $TAG"; exit 1 ;; esac
REPO="ghcr.io/tashfeenahmed/freellmapi"
docker pull -q "$REPO:$TAG" >/dev/null
DIGEST="$(docker buildx imagetools inspect "$REPO:$TAG" --format '{{json .Manifest}}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])')"
case "$DIGEST" in sha256:*) ;; *) echo "::error::could not resolve a digest for $REPO:$TAG"; exit 1 ;; esac
IMAGE="$REPO@$DIGEST"
docker pull -q "$IMAGE" >/dev/null
# smoke test: the container starts and answers its health ping (no provider keys needed for this)
CID="$(docker run -d -p 127.0.0.1:3002:3001 -e ENCRYPTION_KEY="$(openssl rand -hex 32)" "$IMAGE")"
trap 'docker rm -f "$CID" >/dev/null 2>&1 || true' EXIT
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:3002/api/ping >/dev/null 2>&1; then break; fi
  if [ "$i" = 60 ]; then docker logs "$CID" | tail -40; echo "::error::$IMAGE did not start"; exit 1; fi
  sleep 2
done
{
  echo "# FreeLLMAPI container image used by every run (tools/start_freellmapi.sh reads the first non-comment line)."
  echo "# Pinned $(date -u +%F) from tag $TAG by tools/pin_freellmapi.sh (pulled, digest-resolved, health-checked)."
  echo "# To update: run the 'Pin FreeLLMAPI' workflow with a newer release tag and review its pull request."
  echo "$IMAGE"
} > freellmapi.lock
echo "pinned $IMAGE"
