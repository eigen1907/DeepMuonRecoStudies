#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."

uv run python scripts/plot_dataset.py --h5 \
  output/dataset/sim-phase2-d110-v001/test.h5
