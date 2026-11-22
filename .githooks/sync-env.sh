#!/bin/sh
# Sincroniza .env con el archivo de entorno de la rama actual.
# Mapeo: main -> .env.main; dev/Kevin -> .env.dev; cualquier otra rama -> .env.dev

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
[ -n "$branch" ] || exit 0

case "$branch" in
  main)      env_file=".env.main" ;;
  dev|Kevin) env_file=".env.dev" ;;
  *)         env_file=".env.dev" ;;
esac

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

if [ ! -f "$env_file" ]; then
  echo "[hooks] No existe $env_file; se mantiene .env sin cambios." >&2
  exit 0
fi

if cmp -s "$env_file" .env; then
  exit 0
fi

if cp "$env_file" .env; then
  echo "[hooks] Rama '$branch': .env sincronizado desde $env_file"
fi
