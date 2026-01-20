#!/bin/bash
set -e

# Get the UID and GID of the appuser (set during build)
APP_UID=$(id -u appuser 2>/dev/null || echo "1000")
APP_GID=$(id -g appuser 2>/dev/null || echo "1000")

# Fix permissions for the data directory
# This ensures that files created by the container are accessible
# even when the directory is mounted as a volume
if [ -d "/app/data" ]; then
    # Only try to fix permissions if we're running as root
    # (which we should be, since entrypoint runs before USER directive)
    if [ "$(id -u)" = "0" ]; then
        # Set ownership to the app user
        chown -R ${APP_UID}:${APP_GID} /app/data 2>/dev/null || true

        # Set permissions: owner can read/write/execute, group and others can read/execute
        chmod -R 755 /app/data 2>/dev/null || true

        # Ensure the directory itself is writable
        chmod 755 /app/data 2>/dev/null || true
    fi
fi

# Switch to non-root user and execute the command passed as arguments
# Using gosu to switch user (maintains proper signal handling)
# This ensures the application runs as non-root for security
exec gosu appuser "$@"
