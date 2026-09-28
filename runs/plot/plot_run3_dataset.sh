#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."

uv run python scripts/plot_dataset.py --h5 \
  ../../.store/deepmuonreco/dataset/data-run3-muon0-2024cde-v001/test.h5
