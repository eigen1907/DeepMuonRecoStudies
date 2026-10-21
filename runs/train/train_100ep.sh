#!/usr/bin/env bash
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$studies/../DeepMuonReco"

session="100ep-$(date +%y%m%d-%H%M%S)-$$"
zellij attach -b "$session"
for gpu in 0 1 2 3; do
  zellij --session "$session" action new-tab --cwd "$PWD" --name "gpu$gpu" -- \
    env CUDA_VISIBLE_DEVICES="$gpu" uv run python scripts/train.py \
    paths.data_dir="$studies/output/dataset/sim-phase2-d110-v001" \
    paths.log_dir="$studies/output/model" \
    optim.max_epochs=100
done
printf 'zellij attach %s\n' "$session"
