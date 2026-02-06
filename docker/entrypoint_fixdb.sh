#!/bin/sh
set -eu

mkdir -p /app/config /app/logs /app/data

# One-time migration: if legacy DBs exist in /app, move into persisted config dir
for f in users.db tuners.db; do
  if [ -f "/app/$f" ] && [ ! -f "/app/config/$f" ]; then
    mv "/app/$f" "/app/config/$f"
  fi
done

# Force the app's relative DB paths to resolve into /app/config
for f in users.db tuners.db; do
  # If a real file already exists and isn't a symlink, leave it (migration above should prevent this)
  if [ -e "/app/$f" ] && [ ! -L "/app/$f" ]; then
    continue
  fi
  ln -sf "/app/config/$f" "/app/$f"
done

exec "$@"

