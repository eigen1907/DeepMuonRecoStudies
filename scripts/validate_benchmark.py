"""Validate optional benchmark EDM files, or the package's CPU/CUDA score test."""

import argparse
from pathlib import Path

from DataFormats.FWLite import Events, Handle
import numpy as np


MODES = ("baseline", "cpu_nonfilter", "cpu_filter", "gpu_nonfilter", "gpu_filter")
ROOT = Path(__file__).resolve().parents[1]


def event_key(event):
    identity = event.eventAuxiliary().id()
    return (int(identity.run()), int(identity.luminosityBlock()), int(identity.event()))


def product(event, label, typename, process):
    handle = Handle(typename)
    if not event.getByLabel((label, "", process), handle):
        raise ValueError(f"{event_key(event)}: missing {label} in process {process}")
    return handle.product()


def read_scores(event, label="muonIdONNX", process="MUONBENCH", ntracks=None):
    scores = product(event, label, "edm::ValueMap<float>", process)
    if scores.idSize() != 1 or (ntracks is not None and scores.size() != ntracks):
        raise ValueError(f"{event_key(event)}: score map does not describe one complete track collection")
    values = np.array([float(scores.get(index)) for index in range(scores.size())])
    if not np.all(np.isfinite(values)) or not np.all((values == -1) | ((values >= 0) & (values <= 1))):
        raise ValueError(f"{event_key(event)}: invalid probabilities or bypass sentinels")
    return values


def compare_scores(cpu, gpu, threshold):
    if cpu.shape != gpu.shape or not np.array_equal(cpu >= 0, gpu >= 0):
        raise ValueError("CPU/CUDA score counts or evaluation masks differ")
    maximum = float(np.max(np.abs(cpu - gpu), initial=0))
    if not np.allclose(cpu, gpu, atol=1e-5, rtol=1e-4):
        raise ValueError(f"CPU/CUDA scores disagree: max absolute difference {maximum:.3g}")
    cpu_reject = (cpu >= 0) & (cpu < threshold)
    gpu_reject = (gpu >= 0) & (gpu < threshold)
    changed = int(np.count_nonzero(cpu_reject != gpu_reject))
    if changed:
        raise ValueError(f"CPU/CUDA threshold decisions differ for {changed} tracks")
    return maximum


def track_signature(track):
    return tuple(float(value) for value in
                 (track.px(), track.py(), track.pz(), track.vx(), track.vy(), track.vz(), track.charge()))


def read_event(event, mode, process):
    tracks = product(event, "generalTracks", "std::vector<reco::Track>", process)
    track_values = np.array([track_signature(track) for track in tracks])
    muons = product(event, "muons1stStep", "std::vector<reco::Muon>", process)
    signatures, tracker = [], {}
    for muon in muons:
        inner = muon.innerTrack()
        key = int(inner.key()) if inner.isNonnull() else -1
        signature = (float(muon.pt()), float(muon.eta()), float(muon.phi()), int(muon.type()))
        references = tuple(int(ref.key()) if ref.isNonnull() else -1
                           for ref in (inner, muon.outerTrack(), muon.globalTrack()))
        signatures.append((*references, *signature))
        if muon.isTrackerMuon():
            if key < 0 or key >= len(track_values) or key in tracker or not inner.isAvailable():
                raise ValueError(f"{mode}, {event_key(event)}: invalid tracker-muon reference")
            if track_signature(inner.get()) != tuple(track_values[key]):
                raise ValueError(f"{mode}, {event_key(event)}: tracker muon points to a different track collection")
            tracker[key] = signature
    return {"tracks": track_values, "muons": sorted(signatures), "tracker": tracker,
            "scores": None if mode == "baseline" else read_scores(event, process=process, ntracks=len(tracks))}


def event_index(events):
    index = {}
    for number, event in enumerate(events):
        key = event_key(event)
        if key in index:
            raise ValueError(f"Duplicate event identity: {key}")
        index[key] = number
    if not index:
        raise ValueError("No validation events")
    return index


def validate_edm(directory, process, threshold):
    files = {mode: Events(str(directory / mode / "validation.root")) for mode in MODES}
    indices = {mode: event_index(events) for mode, events in files.items()}
    keys = set(indices["baseline"])
    if any(set(index) != keys for index in indices.values()):
        raise ValueError("Validation EDM event identities differ between cases")
    denominator, maximum = 0, 0.0
    retained = dict.fromkeys(("cpu_filter", "gpu_filter"), 0)
    added = retained.copy()
    for key in sorted(keys):
        snapshots = {}
        for mode, events in files.items():
            if not events.to(indices[mode][key]):
                raise ValueError(f"{mode}: cannot seek event {key}")
            snapshots[mode] = read_event(events, mode, process)
        baseline = snapshots["baseline"]
        for mode in MODES[1:]:
            if not np.array_equal(snapshots[mode]["tracks"], baseline["tracks"]):
                raise ValueError(f"{mode}, {key}: reconstruction changed generalTracks")
        for mode in ("cpu_nonfilter", "gpu_nonfilter"):
            if snapshots[mode]["muons"] != baseline["muons"]:
                raise ValueError(f"{mode}, {key}: nonfilter changed final-muon identities or kinematics")
        for suffix in ("nonfilter", "filter"):
            maximum = max(maximum, compare_scores(snapshots["cpu_" + suffix]["scores"],
                                                   snapshots["gpu_" + suffix]["scores"], threshold))
        for device in ("cpu", "gpu"):
            if not np.allclose(snapshots[device + "_nonfilter"]["scores"],
                               snapshots[device + "_filter"]["scores"], atol=1e-7, rtol=1e-6):
                raise ValueError(f"{device}, {key}: changing filter mode changed ONNX scores")
        if snapshots["cpu_filter"]["tracker"] != snapshots["gpu_filter"]["tracker"]:
            raise ValueError(f"{key}: CPU/CUDA filter changed final tracker-muon identities or kinematics")
        baseline_keys = baseline["tracker"].keys()
        denominator += len(baseline_keys)
        for mode in retained:
            selected = snapshots[mode]["tracker"].keys()
            retained[mode] += len(baseline_keys & selected)
            added[mode] += len(selected - baseline_keys)
    print(f"PASS: {len(keys)} events; nonfilter muons unchanged; CPU/CUDA max |score difference| = {maximum:.3g}; cut differences = 0")
    for mode in retained:
        fraction = f"{100 * retained[mode] / denominator:.6f}%" if denominator else "n/a"
        print(f"{mode}: baseline tracker-muon retention {retained[mode]}/{denominator} ({fraction}); new tracker muons = {added[mode]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "output/benchmark")
    parser.add_argument("--process", default="MUONBENCH")
    parser.add_argument("--threshold", type=float, default=0.38735)
    parser.add_argument("--scores", type=Path, help="Validate testMuonIdONNX_cfg.py's two score maps")
    args = parser.parse_args()
    if not np.isfinite(args.threshold) or not 0 <= args.threshold <= 1:
        parser.error("threshold must be a probability between 0 and 1")
    try:
        if args.scores:
            maximum, count = 0.0, 0
            for event in Events(str(args.scores)):
                maximum = max(maximum, compare_scores(read_scores(event, "cpuScores", "ONNXSCORES"),
                                                       read_scores(event, "cudaScores", "ONNXSCORES"), args.threshold))
                count += 1
            if not count:
                raise ValueError("No score-test events")
            print(f"PASS: {count} events; CPU/CUDA max |score difference| = {maximum:.3g}; cut differences = 0")
        else:
            validate_edm(args.input, args.process, args.threshold)
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
