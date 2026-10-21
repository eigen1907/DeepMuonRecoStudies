#!/usr/bin/env bash
# Merge the completed Run3 MC ntuples and convert them with the existing converter.
set -euo pipefail

studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
python="$studies/.venv/bin/python"
store="$HOME/workspace/.store/deepmuonreco"
tag=sim-run3-singlemu-v001
input="$store/chunk/$tag/ntuple"
output="$studies/output/dataset/$tag"
work="$output/.partial"
mkdir -p "$output/filelists" "$work"

"$python" - "$input" "$output/filelists" <<'PY'
from pathlib import Path
import random
import sys

source, destination = map(Path, sys.argv[1:])
files = [source / f"output_{i}.root" for i in range(249)]
if len(list(source.glob("*.root"))) != len(files) or not all(p.is_file() and p.stat().st_size for p in files):
    raise SystemExit("Expected 249 complete Run3 MC ntuples")
random.Random(42).shuffle(files)
# Match the Phase2 dataset: 150k train, 49k validation, 50k test events.
for name, split in (("train", files[:150]), ("val", files[150:199]), ("test", files[199:])):
    path = destination / f"{name}.txt"
    content = "".join(f"{p}\n" for p in split)
    if path.exists() and path.read_text() != content:
        raise SystemExit(f"Existing file list differs: {path}")
    path.write_text(content)
    print(f"{name}: {len(split)} files", flush=True)
PY

for split in train val test; do
  if [[ -s $output/$split.root && -s $output/$split.h5 ]]; then
    echo "Already complete: $split"
    continue
  fi
  [[ ! -e $output/$split.root && ! -e $output/$split.h5 ]] || {
    echo "Incomplete final outputs for $split; inspect $output" >&2
    exit 1
  }
  rm -f -- "$work/$split.root" "$work/$split.h5"
  apptainer exec --cleanenv --bind "$HOME:$HOME" \
    "$store/containers/cmssw-el8.sif" \
    bash -s -- "$work/$split.root" "$output/filelists/$split.txt" <<'IN_CONTAINER'
set -euo pipefail
export SCRAM_ARCH=el8_amd64_gcc12
set +u
source "$HOME/workspace/deepmuonreco/CMSSW/runtime/cmsset_default.sh"
set -u
cd "$HOME/workspace/deepmuonreco/CMSSW/CMSSW_14_0_21_patch1/src"
runtime=$(scram runtime -sh)
eval "$runtime"
hadd "$1" "@$2"
IN_CONTAINER
  "$python" -u "$studies/scripts/convert-root-to-hdf5.py" \
    --input "$work/$split.root" --step-size "256 MB"
  mv "$work/$split.root" "$work/$split.h5" "$output/"
  echo "DONE $split"
done
rmdir "$work"
