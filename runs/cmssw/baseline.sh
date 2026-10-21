#!/usr/bin/env bash
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
workspace=$(dirname -- "$studies")
output="$studies/output/plots/cmssw/phase2-d110/baseline-01"
mkdir -p "$output"

# Run after runs/plot/validate_onnx.sh. This step only builds and checks CMSSW.
apptainer exec --cleanenv --bind "$HOME:$HOME" \
  "$HOME/workspace/.store/deepmuonreco/containers/cmssw-el8.sif" \
  bash -s -- "$workspace" <<'CMSSW' 2>&1 | tee "$output/run.log"
set -eo pipefail
workspace=$1
export SCRAM_ARCH=el8_amd64_gcc12
source "$workspace/CMSSW/runtime/cmsset_default.sh"
cd "$workspace/CMSSW/CMSSW_14_0_9/src"
runtime=$(scram runtime -sh)
eval "$runtime"

ln -sfn "$workspace/DeepMuonRecoSample" DeepMuonRecoSample
scram b -j 4
cmsRun "$workspace/DeepMuonRecoSample/Inference/test/run_cfg.py"
CMSSW
