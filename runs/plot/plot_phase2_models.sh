#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."

uv run python scripts/plot_model.py \
  --h5 ../../.store/deepmuonreco/dataset/sim-phase2-d110-v001/test.h5 \
  --model ../DeepMuonReco/logs/phase2-d110/baseline-01
