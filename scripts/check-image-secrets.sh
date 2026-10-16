#!/usr/bin/env bash
# Inspect a disposable container; report paths only, never secret contents.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/check-image-secrets.sh <image>" >&2
  exit 2
fi
image=$1
volumes=$(docker image inspect --format '{{range $path, $_ := .Config.Volumes}}{{println $path}}{{end}}' "$image")
data_dirs=(/app /data /uploads /var/lib)
while IFS= read -r path; do
  [[ -z "$path" ]] || data_dirs+=("$path")
done <<< "$volumes"

# Root can inspect files owned by any runtime account. No network or host mounts.
MSYS_NO_PATHCONV=1 docker run --rm --network none --user 0 --entrypoint sh -i "$image" -s -- "${data_dirs[@]}" <<'SCAN'
set -eu
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
failed=0

scan_names() {
  # Do not follow symlinks: the distribution's public CA links are not secrets.
  # Scan declared volumes separately because -xdev does not cross mounts.
  if ! find "$1" -xdev \
    \( -path /proc -o -path '/proc/*' -o -path /sys -o -path '/sys/*' -o -path /usr -o -path '/usr/*' \) -prune -o \
    -type f \( -name '.env' -o -name '.env.*' -o -name '*.dump' \
      -o -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.pfx' \
      -o -name '*.sql.gz' -o -name 'id_rsa*' -o -name 'id_ed25519*' \) \
    ! -name '.env.example' -print > "$scratch/names"; then
    echo "Could not complete filename scan: $1" >&2
    exit 2
  fi
  if [ -s "$scratch/names" ]; then
    echo 'Secret-like file paths:' >&2
    cat "$scratch/names" >&2
    failed=1
  fi
}

scan_names /
for directory in "$@"; do
  [ -d "$directory" ] || continue
  case "$directory" in /proc|/proc/*|/sys|/sys/*|/usr|/usr/*) continue ;; esac
  scan_names "$directory"
  # BusyBox grep (Alpine) has no --exclude-dir; prune before inspecting files.
  if ! find "$directory" -type d -name node_modules -prune -o -type f -exec sh -c '
    for file do
      result=0
      grep -lsE "BEGIN ([A-Z]+ )?PRIVATE KEY" "$file" || result=$?
      [ "$result" -le 1 ] || exit 2
    done
  ' sh {} + > "$scratch/content"; then
    echo "Could not complete private-key content scan: $directory" >&2
    exit 2
  fi
  if [ -s "$scratch/content" ]; then
    echo 'Private-key content found in:' >&2
    cat "$scratch/content" >&2
    failed=1
  fi
done
exit "$failed"
SCAN
echo "PASS: no secret-like files or private-key content in $image"
