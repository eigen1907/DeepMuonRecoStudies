#!/usr/bin/env bash
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$studies/../DeepMuonReco"

session="sanity-$(date +%y%m%d-%H%M%S)-$$"
zellij attach -b "$session"
zellij --session "$session" run --cwd "$PWD" --name train -- \
  env CUDA_VISIBLE_DEVICES=0 uv run python scripts/train.py mode=sanity-check \
  paths.data_dir="$studies/output/dataset/sim-phase2-d110-v001" \
  paths.log_dir="$studies/output/model"
printf 'zellij attach %s\n' "$session"
