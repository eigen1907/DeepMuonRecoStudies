#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../DeepMuonReco"

session="default-$(date +%y%m%d-%H%M%S)-$$"
zellij attach -b "$session"
for gpu in 0 1 2 3; do
  zellij --session "$session" action new-tab --cwd "$PWD" --name "gpu$gpu" -- \
    env CUDA_VISIBLE_DEVICES="$gpu" uv run python scripts/train.py \
    paths.data_dir=/users/hep/joshin/workspace/.store/deepmuonreco/dataset/sim-phase2-d110-v001
done
printf 'zellij attach %s\n' "$session"
