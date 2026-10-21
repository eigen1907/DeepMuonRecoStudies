#!/usr/bin/env bash
set -euo pipefail
studies=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
export remote=${DMR_REMOTE:-joshin@gate.sscc.uos.ac.kr}
export ssh_port=${DMR_SSH_PORT:-22}
export remote_root=/hdfs/store/mc/Phase2Spring24DIGIRECOMiniAOD/SingleMu_FlatPt-2to100/GEN-SIM-DIGI-RAW-MINIAOD/PU200_Trk1GeV_140X_mcRun4_realistic_v4-v2
export output="$studies/output/sample/Phase2/MC/singlemu-d110-pu200/raw"
mkdir -p "$output/logs"

if [[ ${1:-} != worker ]]; then
  zellij attach -b fetch-phase2 2>/dev/null || true
  zellij --session fetch-phase2 run --cwd "$studies" --name rsync -- \
    env DMR_REMOTE="$remote" DMR_SSH_PORT="$ssh_port" bash "$0" worker
  echo "Download session: zellij attach fetch-phase2 (16 workers)"
  echo "Logs: $output/logs"
  exit
fi

exec 9>"$output/.fetch.lock"
flock -n 9 || { echo "Phase2 download is already running." >&2; exit 1; }
rm -f "$output/logs/exitcode"
echo "$$" >"$output/logs/fetch.pid"
exec >"$output/logs/fetch.log" 2>&1
set +e
date -Is
until ssh -n -p "$ssh_port" -o BatchMode=yes -o ConnectTimeout=20 "$remote" \
  "set -o pipefail; find '$remote_root' -type f -name '*.root' -printf '%s\\t%p\\n' | sort -n" >"$output/manifest.tsv.tmp"; do
  echo "SSH unavailable; retrying in 60 seconds."
  sleep 60
done
mv "$output/manifest.tsv.tmp" "$output/manifest.tsv"
awk -F "\t" "{print NR-1; print \$2}" "$output/manifest.tsv" | xargs -d '\n' -r -n2 -P16 bash -c '
    # Stagger SSH handshakes to avoid connection rejections seen during a burst.
    sleep "$(( $1 % 16 ))"
    file=$2
    name=${file##*/}
    rm -f "$output/logs/$name.exitcode"
    date -Is >"$output/logs/$name.log"
    for attempt in 1 2 3; do
      rsync --times --partial-dir=.rsync-partial --protect-args --info=progress2 \
        -e "ssh -p $ssh_port -o BatchMode=yes -o ConnectTimeout=20" \
        "$remote:$file" "$output/" >>"$output/logs/$name.log" 2>&1
      status=$?
      (( status == 0 )) && break
      sleep 10
    done
    echo "$status" >"$output/logs/$name.exitcode"
    echo "$name: exit $status"
    exit "$(( status != 0 ))"
  ' _
status=$?
echo "$status" >"$output/logs/exitcode"
date -Is
exit "$status"
