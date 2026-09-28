#!/usr/bin/env bash
set -euo pipefail
sample=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../DeepMuonRecoSample" && pwd)
exec bash "$sample/Run3/slurm/submit_data_ntuple.sh" "$@"
