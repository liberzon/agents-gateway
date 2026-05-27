#!/usr/bin/env bash

set -e
set -o pipefail

echo ">>> Installing dependencies (ruff, mypy) if missing"
pip install ruff mypy

echo ">>> Running ruff format to auto-fix formatting issues"
ruff format .

echo ">>> Running ruff check with --fix to auto-fix lint issues"
ruff check . --fix

echo ">>> Running mypy for type checking"
if [ -d ".venv" ]; then
    VIRTUAL_ENV=.venv .venv/bin/python -m mypy . --config-file pyproject.toml
else
    mypy .
fi

echo ">>> ✅ All done!"
