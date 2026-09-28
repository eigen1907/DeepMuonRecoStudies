#!/usr/bin/env bash
set -euo pipefail
sample=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../DeepMuonRecoSample" && pwd)

store="$HOME/workspace/.store/deepmuonreco/chunk/Run3/MC"
tag=run3-singlemu-premix-v001
signal="$store/run3-singlemu-gensim-v002/gensim"
minbias="$store/run3-minbias-v001/minbias"

case $#:${1:-} in
  1:gensim) bash "$sample/Run3/slurm/submit_gensim.sh" ;;
  1:minbias) bash "$sample/Run3/slurm/submit_gensim.sh" --minbias 2490 ;;
  1:premix) bash "$sample/Run3/slurm/submit_processing.sh" premix "$tag" "$signal" "$minbias" ;;
  1:digiraw) bash "$sample/Run3/slurm/submit_processing.sh" digiraw "$tag" "$signal" ;;
  1:reco|1:ntuple) bash "$sample/Run3/slurm/submit_processing.sh" "$1" "$tag" ;;
  *) echo "Usage: $0 {gensim|minbias|premix|digiraw|reco|ntuple}" >&2; exit 2 ;;
esac
