#!/usr/bin/env bash
# Usage: bash runs/benchmark/run.sh CASE|all RAW_INPUT [EVENTS=100] [THRESHOLD=0.38735]
set -eo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
workspace=$(dirname -- "$studies")
mode=${1:-}
input=${2:-}
events=${3:-100}
threshold=${4:-0.38735}
case "$mode" in
  baseline|cpu_nonfilter|cpu_filter|gpu_nonfilter|gpu_filter) modes=("$mode") ;;
  all) modes=(baseline cpu_nonfilter cpu_filter gpu_nonfilter gpu_filter) ;;
  *) echo "Usage: $0 CASE|all RAW_INPUT [EVENTS=100] [THRESHOLD=0.38735]" >&2; exit 2 ;;
esac
[[ -n "$input" ]] || { echo "Pass the original, fully transferred RAW file." >&2; exit 2; }

input=$(python3 - "$input" "$events" "$threshold" <<'PY'
import math
import os
import struct
import sys

value, events, threshold = sys.argv[1:]
if int(events) < -1:
    sys.exit("EVENTS must be -1 (all events), 0, or positive")
if not math.isfinite(float(threshold)) or not 0 <= float(threshold) <= 1:
    sys.exit("THRESHOLD must be a probability between 0 and 1")
if value.startswith("root://"):
    print(value)
else:
    path = os.path.abspath(value.removeprefix("file:"))
    with open(path, "rb") as source:
        header = source.read(32)
    if len(header) < 20 or header[:4] != b"root":
        sys.exit("Not a ROOT file: " + path)
    version = struct.unpack(">I", header[4:8])[0]
    expected = struct.unpack(">Q", header[12:20])[0] if version >= 1000000 else struct.unpack(">I", header[12:16])[0]
    if os.path.getsize(path) < expected:
        sys.exit("Input transfer incomplete: " + path)
    print("file:" + path)
PY
)

for run_mode in "${modes[@]}"; do
  area=onnx
  backend=cpu
  [[ "$run_mode" != gpu_* ]] || backend=cuda
  if [[ "$run_mode" == baseline ]]; then
    area=base
    backend=none
  fi
  output="$studies/output/benchmark/$run_mode"
  mkdir -p "$output"
  printf '%s\n' "mode=$run_mode" "input=$input" "maxEvents=$events" \
    "threshold=$threshold" "backend=$backend" > "$output/settings.txt"
  if [[ "$run_mode" != baseline ]]; then
    printf 'modelSHA256=%s\n' "$(sha256sum "$studies/data/model.onnx" | cut -d ' ' -f 1)" >> "$output/settings.txt"
  fi
  rm -f "$output/resources.json"
  printf 'Running %s (%s events)...\n' "$run_mode" "$events"
  (
    export SCRAM_ARCH=el9_amd64_gcc12
    source /cvmfs/cms.cern.ch/cmsset_default.sh
    cd "$workspace/cmssw/$area/CMSSW_14_0_9/src"
    eval "$(scram runtime -sh)"
    cd "$output"
    if ! /usr/bin/time -v -o time.txt cmsRun "$studies/runs/benchmark/run_cfg.py" \
      "mode=$run_mode" "inputFiles=$input" "maxEvents=$events" \
      "threshold=$threshold" "modelPath=$studies/data/model.onnx" > run.log 2>&1; then
      tail -n 30 run.log >&2
      echo "Full log: $output/run.log" >&2
      exit 1
    fi
    python3 - "$run_mode" "$events" <<'PY'
import json
import sys

mode, requested = sys.argv[1], int(sys.argv[2])
result = json.load(open("resources.json"))
completed = result["total"]["events"]
if requested > 0 and completed != requested:
    sys.exit(f"Incomplete run: requested {requested}, completed {completed}")
required = ["recoProducts", "muons1stStep"] + ([] if mode == "baseline" else ["muonIdONNX"])
counts = {row["label"]: row["events"] for row in result["modules"]}
if requested != 0 and (completed == 0 or any(counts.get(label) != completed for label in required)):
    sys.exit("Reconstruction did not execute for every event: " + str({label: counts.get(label, 0) for label in required}))
PY
  )
done
if [[ "$mode" == all && "$events" != 0 ]]; then
  (
    export SCRAM_ARCH=el9_amd64_gcc12
    source /cvmfs/cms.cern.ch/cmsset_default.sh
    cd "$workspace/cmssw/base/CMSSW_14_0_9/src"
    eval "$(scram runtime -sh)"
    python3 "$studies/scripts/plot_benchmark.py"
  )
else
  echo "Saved: $output"
fi
