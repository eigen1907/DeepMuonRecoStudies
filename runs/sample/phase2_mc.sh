#!/usr/bin/env bash
set -euo pipefail
sample=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../DeepMuonRecoSample" && pwd)

tag=phase2-mc-v001
case ${1:-} in
  rereco)
    [[ $# == 2 ]] || { echo "Usage: $0 rereco INPUT_LIST" >&2; exit 2; }
    bash "$sample/Phase2/slurm/submit_rereco.sh" "$2" "$tag"
    ;;
  ntuple)
    [[ $# == 1 ]] || { echo "Usage: $0 ntuple" >&2; exit 2; }
    bash "$sample/Phase2/slurm/submit_ntuple.sh" "$tag"
    ;;
  *) echo "Usage: $0 {rereco INPUT_LIST|ntuple}" >&2; exit 2 ;;
esac
