#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

echo "[omnismi:init] repo=$ROOT_DIR"
echo "[omnismi:init] python=$PYTHON_BIN"
"$PYTHON_BIN" --version

echo "[omnismi:init] recent commits"
git log --oneline -5 || true

if [[ "${OMNISMI_SKIP_INSTALL:-0}" != "1" ]]; then
  echo "[omnismi:init] refreshing editable install"
  "$PYTHON_BIN" -m pip install -e ".[dev]" >/dev/null
fi

echo "[omnismi:init] validating feature catalog JSON"
"$PYTHON_BIN" -m json.tool feature_list.json >/dev/null

echo "[omnismi:init] import smoke check"
PYTHONPATH=src "$PYTHON_BIN" - <<'PY'
import omnismi as omi

print(
    {
        "version": omi.__version__,
        "exports": list(omi.__all__),
        "gpu_count": omi.count(),
    }
)
PY

echo "[omnismi:init] unit tests"
PYTHONPATH=src "$PYTHON_BIN" -m pytest -q

echo "[omnismi:init] bytecode compile smoke check"
"$PYTHON_BIN" -m compileall src tests >/dev/null

if [[ "${OMNISMI_RUN_DOCS:-0}" == "1" ]]; then
  echo "[omnismi:init] docs build"
  "$PYTHON_BIN" -m mkdocs build --strict
fi

if [[ "${OMNISMI_RUN_PARITY:-0}" == "1" ]]; then
  echo "[omnismi:init] optional parity checks"
  for vendor in nvidia amd; do
    PYTHONPATH=src "$PYTHON_BIN" -m omnismi.validation.parity --vendor "$vendor" --samples 3
  done
else
  echo "[omnismi:init] parity checks skipped"
  echo "  Set OMNISMI_RUN_PARITY=1 to compare against vendor libraries on supported hardware."
fi
