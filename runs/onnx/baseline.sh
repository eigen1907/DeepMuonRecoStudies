#!/usr/bin/env bash
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
model_repo="$(dirname -- "$studies")/DeepMuonReco"
PYTHONPATH="$model_repo/src" "$model_repo/.venv/bin/python" \
  "$studies/scripts/export_onnx.py"
