#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python is required. No installation was attempted." >&2
  exit 2
fi

exec "$PYTHON" "$SCRIPT_DIR/sync-agent-skills.py" "$@"
