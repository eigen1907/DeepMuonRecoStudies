#!/usr/bin/env bash
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
model_repo="$(dirname -- "$studies")/DeepMuonReco"
output="$studies/output/plots/onnx/phase2-d110/baseline-01"
mkdir -p "$output"

PYTHONPATH="$model_repo/src" "$model_repo/.venv/bin/python" \
  "$studies/scripts/validate_onnx.py" 2>&1 | tee "$output/validation.log"
