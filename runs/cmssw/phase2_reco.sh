#!/usr/bin/env bash
# Usage: bash runs/cmssw/phase2_reco.sh file:/path/to/phase2-raw.root
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
workspace=$(dirname -- "$studies")
input=${1:?Pass a Phase-2 D110 EDM input, e.g. file:/path/to/input.root}
output="$studies/output/plots/cmssw/phase2-d110/baseline-01/reco"
mkdir -p "$output"

apptainer exec --cleanenv --bind "$HOME:$HOME" \
  "$HOME/workspace/.store/deepmuonreco/containers/cmssw-el8.sif" \
  bash -s -- "$workspace" "$input" "$output" <<'CMSSW' 2>&1 | tee "$output/run.log"
set -eo pipefail
workspace=$1
input=$2
output=$3
export SCRAM_ARCH=el8_amd64_gcc12
source "$workspace/CMSSW/runtime/cmsset_default.sh"
cd "$workspace/CMSSW/CMSSW_14_0_9/src"
eval "$(scram runtime -sh)"
scram b -j 4
cd "$output"
cmsRun "$workspace/DeepMuonRecoSample/Inference/test/run_phase2_cfg.py" \
  inputFiles="$input" outputFile=reco.root maxEvents=10
CMSSW
