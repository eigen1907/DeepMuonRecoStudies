"""Dataset plots from H5 ntuples, using the stored good-track selection.

Run from the repository root with ``uv run python scripts/plot_dataset.py``.
All events are processed by default, reading 128 events at a time.
"""

import argparse
from pathlib import Path

import h5py
import hist
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np

from plot_style import color_scale


plt.style.use(hep.style.CMS)
STORE = Path(__file__).resolve().parents[3] / ".store/deepmuonreco/dataset"
OUTPUT = Path(__file__).resolve().parents[1] / "plots"
PRIMITIVES = {
    "dt": "dt_seg_pos_x", "csc": "csc_seg_pos_x", "gem_seg": "gem_seg_pos_x",
    "rpc": "rpc_hit_pos_x", "gem_hit": "gem_hit_pos_x",
}
PT_EDGES = np.linspace(0, 10, 101)
ETA_EDGES = np.linspace(-3, 3, 61)
CHUNK_EVENTS = 128


def read_sample(path, phase2):
    """Read needed branches in event chunks; retain counts and 2D bin sums."""
    with h5py.File(path) as file:
        total = len(file["track_is_trk_muon"])
        stop = total
        truth = all(k in file for k in ("track_is_matched_muon", "tp_pdg_id", "tp_status"))
        if truth:
            probe = slice(0, min(stop, 8))
            truth = any(len(x) for x in file["tp_pdg_id"][probe]) and any(
                np.any(x >= 0) for x in file["track_is_matched_muon"][probe]
            )
        keys = {"track_is_trk_muon", "track_is_good_track", *PRIMITIVES.values()}
        if phase2:
            keys.update(("track_pt", "track_eta"))
        if truth:
            keys.update(("track_is_matched_muon", "tp_pdg_id", "tp_status"))

        counts = {key: [] for key in ("tracks", "tracker_muons", "matched_muons", "truth_muons", *PRIMITIVES)}
        maps = {
            key: np.zeros((100, 60), dtype=np.float64)
            for key in ("tracks", "tracker_muons", "truth_matched")
        } if phase2 else {}

        for start in range(0, stop, CHUNK_EVENTS):
            end = min(stop, start + CHUNK_EVENTS)
            chunk = {key: file[key][start:end] for key in keys}
            points = {key: ([], []) for key in maps}
            for i in range(end - start):
                muon = chunk["track_is_trk_muon"][i] == 1
                selected = chunk["track_is_good_track"][i] == 1
                counts["tracks"].append(int(np.count_nonzero(selected)))
                counts["tracker_muons"].append(int(np.count_nonzero(selected & muon)))
                for name, branch in PRIMITIVES.items():
                    counts[name].append(len(chunk[branch][i]))
                if truth:
                    matched = chunk["track_is_matched_muon"][i] == 1
                    pdg, status = chunk["tp_pdg_id"][i], chunk["tp_status"][i]
                    counts["matched_muons"].append(int(np.count_nonzero(selected & matched)))
                    counts["truth_muons"].append(int(np.count_nonzero((np.abs(pdg) == 13) & (status == 1))))
                if phase2:
                    pt, eta = chunk["track_pt"][i], chunk["track_eta"][i]
                    valid = selected & np.isfinite(pt) & np.isfinite(eta)
                    categories = {"tracks": valid, "tracker_muons": valid & muon}
                    if truth:
                        categories["truth_matched"] = valid & matched
                    for name, mask in categories.items():
                        points[name][0].append(pt[mask])
                        points[name][1].append(eta[mask])
            for name, (pt_parts, eta_parts) in points.items():
                if pt_parts:
                    maps[name] += np.histogram2d(
                        np.concatenate(pt_parts), np.concatenate(eta_parts),
                        bins=(PT_EDGES, ETA_EDGES),
                    )[0]
        print(f"{path.name}: {stop} events, truth {'available' if truth else 'unavailable'}")

    counts = {name: np.asarray(values) for name, values in counts.items()}
    counts["dt_csc"] = counts["dt"] + counts["csc"]
    counts["segments"] = counts["dt_csc"] + counts["gem_seg"]
    counts["hits"] = counts["rpc"] + counts["gem_hit"]
    counts["primitives"] = counts["dt_csc"] + counts["hits"]
    return counts, maps, truth


def bins_for(*arrays):
    top = float(np.percentile(np.concatenate(arrays), 99.5)) * 1.05
    if top <= 0:
        return 25, 0, 1
    scale = 10 ** np.floor(np.log10(top))
    edge = next(x for x in (1, 2, 2.5, 5, 10) if top <= x * scale)
    return 25, 0, edge * scale


def save_hist(output, items, xlabel, title, com, data, bins=None):
    """items are (values, legend label, color); the whole image has one Axes."""
    bins = bins or bins_for(*(values for values, _, _ in items))
    fig, ax = plt.subplots(figsize=(10, 8))
    for values, label, color in items:
        h = hist.Hist(hist.axis.Regular(*bins))
        h.fill(values)
        h.plot(ax=ax, density=True, yerr=True, histtype="step", linewidth=2.5,
               label=f"{label}\n<N>: {np.mean(values):.1f}", color=color)
    ax.set(xlim=(bins[1], bins[2]), ylim=(0, None), xlabel=xlabel, ylabel="Normalized")
    ax.legend(title=title)
    fig.tight_layout()
    hep.cms.label("Private Work", ax=ax, data=data, com=com, fontsize=24)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(output)


def save_map(output, counts, com, kind):
    if counts.sum() == 0:
        return
    density = counts / (counts.sum() * np.diff(PT_EDGES)[0] * np.diff(ETA_EDGES)[0])
    maximum = float(density.max())
    fig, ax = plt.subplots(figsize=(10, 8))
    image = ax.pcolormesh(PT_EDGES, ETA_EDGES, np.ma.masked_equal(density.T, 0),
                          cmap="viridis", vmin=0, vmax=maximum, shading="auto")
    label = {"tracks": "Tracker Track", "tracker_muons": "Tracker Muon",
             "truth_matched": "Truth-Matched Track"}[kind]
    ax.set(xlim=(0, 10), ylim=(-3, 3), xlabel=rf"{label} $p_T$ [GeV]",
           ylabel=rf"{label} $\eta$")
    fig.subplots_adjust(left=0.12, right=0.76, bottom=0.12, top=0.88)
    hep.cms.label("Private Work", ax=ax, data=False, com=com, fontsize=24)
    color_scale(ax, image, "Normalized")
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(output)


def save_sample(name, counts, maps, truth, output_dir):
    data = name == "run3"
    title = "Run 3 Muon0 data (2024CDE)" if data else r"$\mu^{+}\mu^{-}$ + 200 PU"
    com = 13.6 if data else 14.0
    red = "#e43d42"
    objects = [("tracks", "Tracker Tracks", "C0"), ("tracker_muons", "Tracker Muons", red)]
    if truth:
        objects += [("matched_muons", "Matched Muons", "C2"), ("truth_muons", "Truth Muons", red)]
    for key, label, color in objects:
        bins = (3, -0.5, 2.5) if key in ("matched_muons", "truth_muons") else None
        save_hist(output_dir / f"{name}_{key}.png", [(counts[key], label, color)],
                  "Number of Objects", title, com, data, bins)
    for filename, xlabel, items in (
        ("segments", "Number of Segments", [("dt", "DT", "C0"), ("csc", "CSC", "C1"),
                                            ("gem_seg", "GEM", "C2"), ("segments", "All Segments", "C3")]),
        ("hits", "Number of Hits", [("rpc", "RPC", "C0"), ("gem_hit", "GE1/1 & GE2/1", "C1"),
                                     ("hits", "All Hits", "C2")]),
        ("primitives", "Number of Objects", [("dt_csc", "DT & CSC Segments", "C0"),
                                              ("hits", "RPC & GEM Hits", "C1"),
                                              ("primitives", "All Muon Detector Primitives", red)]),
    ):
        save_hist(output_dir / f"{name}_{filename}.png",
                  [(counts[key], label, color) for key, label, color in items], xlabel, title, com, data)
    for key, image in maps.items():
        if key != "truth_matched" or truth:
            save_map(output_dir / f"{name}_{key}_pt_eta.png", image, com, key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5", type=Path,
                        default=STORE / "sim-phase2-d110-v001/test.h5")
    args = parser.parse_args()
    output = OUTPUT / "dataset"
    output.mkdir(parents=True, exist_ok=True)
    name = "run3" if "run3" in str(args.h5).lower() else "phase2"
    counts, maps, truth = read_sample(args.h5, name == "phase2")
    save_sample(name, counts, maps, truth, output)


if __name__ == "__main__":
    main()
