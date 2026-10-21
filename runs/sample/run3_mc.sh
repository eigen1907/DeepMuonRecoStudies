#!/usr/bin/env bash
set -euo pipefail

sample=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../DeepMuonRecoSample" && pwd)

store="$HOME/workspace/.store/deepmuonreco/chunk"
tag="sim-run3-singlemu-v001"

gensim="$store/$tag/gensim"
minbias="$store/$tag/minbias"

case $#:${1:-} in
  1:gensim)
    bash "$sample/Run3/slurm/submit_gensim.sh"
    ;;

  1:minbias)
    bash "$sample/Run3/slurm/submit_gensim.sh" --minbias 2490
    ;;

  1:premix)
    bash "$sample/Run3/slurm/submit_processing.sh" \
      premix "$tag" "$gensim" "$minbias"
    ;;

  1:digiraw)
    bash "$sample/Run3/slurm/submit_processing.sh" \
      digiraw "$tag" "$gensim"
    ;;

  1:reco|1:ntuple)
    bash "$sample/Run3/slurm/submit_processing.sh" \
      "$1" "$tag"
    ;;

  *)
    echo "Usage: $0 {gensim|minbias|premix|digiraw|reco|ntuple}" >&2
    exit 2
    ;;
esac