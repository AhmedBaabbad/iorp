#!/usr/bin/env bash
# Synthetic fixtures only. Never include a real credential in these images.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/test-check-image-secrets.sh <base-image>" >&2
  exit 2
fi
base=$1
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
context=$(mktemp -d)
prefix="iorp/secret-scan-regression:$$"
images=()
cleanup() {
  rm -rf "$context"
  if [[ ${#images[@]} -gt 0 ]]; then docker image rm "${images[@]}" >/dev/null; fi
}
trap cleanup EXIT

fixture() {
  local name=$1 instruction=$2 expected=$3
  local image="${prefix}-${name}"
  images+=("$image")
  # Docker expands BASE; the shell must leave it literal in the Dockerfile.
  # shellcheck disable=SC2016
  printf 'ARG BASE\nFROM ${BASE}\nUSER 0\n%s\n' "$instruction" > "$context/Dockerfile"
  docker build --quiet --build-arg "BASE=$base" -t "$image" "$context" >/dev/null
  local result=0
  bash "$script_dir/check-image-secrets.sh" "$image" > "$context/result" 2>&1 || result=$?
  if [[ "$result" -ne "$expected" ]]; then
    cat "$context/result" >&2
    echo "FAIL: $name returned $result, expected $expected" >&2
    exit 1
  fi
  echo "PASS: $name (exit $result)"
}

fixture public-ca-links "RUN mkdir -p /usr/share/scan-test /etc/ssl/certs; printf public > /usr/share/scan-test/ca.crt; ln -s /usr/share/scan-test/ca.crt /etc/ssl/certs/scan-test.pem; printf example > /app/.env.example" 0
fixture env-file "RUN printf synthetic > /app/.env" 1
fixture real-ssl-pem "RUN mkdir -p /etc/ssl/certs; printf synthetic > /etc/ssl/certs/scan-test.pem" 1
fixture key-content "RUN printf '%s\\n' '-----BEGIN PRIVATE KEY-----' synthetic > /app/scan-test.txt" 1
fixture volume-content $'RUN mkdir /scan-data; printf "%s\\n" "-----BEGIN RSA PRIVATE KEY-----" synthetic > /scan-data/record.txt\nVOLUME ["/scan-data"]' 1
