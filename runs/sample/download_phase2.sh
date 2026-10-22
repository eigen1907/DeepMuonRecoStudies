#!/usr/bin/env bash
# Download one verified Phase2 file by default; explicit names select other files.
# Interrupted .part files can be resumed.
# Usage: bash runs/sample/download_phase2.sh [BASENAME ...]
set -eo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
output=${PHASE2_RECO_DIR:-/eos/user/${USER:0:1}/$USER/deepmuonreco/phase2/reco}
logs="$studies/output/benchmark/downloads"
endpoint=${PHASE2_SOURCE_ENDPOINT:-root://cms-xrd-global.cern.ch}
prefix=/store/mc/Phase2Spring24DIGIRECOMiniAOD/SingleMu_FlatPt-2to100/GEN-SIM-DIGI-RAW-MINIAOD/PU200_Trk1GeV_140X_mcRun4_realistic_v4-v2/2820000
mkdir -p "$output" "$logs"

export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
cd "$studies/../cmssw/base/CMSSW_14_0_9/src"
eval "$(scram runtime -sh)"
export XRD_CPTIMEOUT=43200 XRD_CPINITTIMEOUT=300

if [[ $# == 0 ]]; then
  set -- 41ea10ad-0471-4681-8bb1-140d3759674a.root
fi

verify() {
  python3 - "$1" "$bytes" <<'PY'
import os, struct, sys
path, expected = sys.argv[1], int(sys.argv[2])
with open(path, "rb") as source:
    header = source.read(32)
if header[:4] != b"root" or os.path.getsize(path) != expected:
    sys.exit("ROOT file size does not match DBS: " + path)
version = struct.unpack(">I", header[4:8])[0]
end = struct.unpack(">Q" if version >= 1000000 else ">I", header[12:20] if version >= 1000000 else header[12:16])[0]
if end != expected:
    sys.exit("ROOT header does not match DBS: " + path)
PY
  actual=$(xrdfs root://eosuser.cern.ch query checksum "$1" | awk '{print $NF}')
  [[ "$actual" == "$checksum" ]] || { echo "Checksum mismatch: $actual != $checksum" >&2; return 1; }
  timeout 300 edmFileUtil -j "file:$1" > "$logs/$name.json"
  python3 - "$logs/$name.json" <<'PY'
import json, sys
records = json.load(open(sys.argv[1]))
if len(records) != 1 or records[0]["events"] != 1000:
    sys.exit("Expected 1000 readable events")
print("Verified: 1000 events, full ROOT size, DBS adler32 checksum")
PY
}

for name in "$@"; do
  # Exact sizes and checksums from DBS for these original files.
  case "$name" in
    41ea10ad-0471-4681-8bb1-140d3759674a.root) bytes=51519055417; checksum=6d5a562f ;;
    dfe749df-7cf5-44a3-8e0b-e3842209a062.root) bytes=51515102576; checksum=8ea22ca5 ;;
    edbcdb38-284c-419b-97b2-bc17f503add5.root) bytes=51418347931; checksum=30627f81 ;;
    *) echo "Unknown source file: $name" >&2; exit 2 ;;
  esac
  exec 9> "/tmp/deepmuonreco-$USER-$name.lock"
  flock -n 9 || { echo "Already downloading: $name" >&2; exit 1; }
  target="$output/$name"
  partial="$target.part"
  if [[ -f "$target" && $(stat -c %s "$target") == "$bytes" ]] && verify "$target"; then
    echo "Already complete: $target"
    continue
  fi
  options=()
  [[ ! -f "$partial" ]] || options=(--continue)
  echo "$(date -Is) Downloading $name ($bytes bytes)"
  timeout 12h xrdcp "${options[@]}" --cksum "adler32:$checksum" \
    --retry 2 --retry-policy continue --nopbar \
    "$endpoint/$prefix/$name" "root://eosuser.cern.ch/$partial"
  verify "$partial"
  mv -f -- "$partial" "$target"
  echo "$(date -Is) Complete: $target"
done
