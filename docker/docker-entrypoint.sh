#!/bin/sh
# Entrypoint for the platform-service container.
#
# Runs as root only to guarantee the local file-storage directory exists and is
# writable by the non-root application user, then drops privileges to appuser.
#
# This makes the container robust against fresh/named volumes mounted at
# FILE_STORAGE_LOCAL_BASE_PATH (which are created as root:root by Docker),
# avoiding "Permission denied" errors on file upload after `docker compose down -v`.
set -eu

STORAGE_PATH="${FILE_STORAGE_LOCAL_BASE_PATH:-/data/files}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$STORAGE_PATH"
    chown -R appuser:appuser "$STORAGE_PATH" 2>/dev/null || true
    exec gosu appuser "$@"
fi

exec "$@"
