"""Draw slide-style plots for one model on the full test H5."""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import subprocess

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import mplhep as hep
import numpy as np

from study_h5 import iter_scored_chunks


plt.style.use(hep.style.CMS)
ROOT = Path(__file__).resolve().parents[1]
MODEL_REPO = ROOT.parent / "DeepMuonReco"
TEST = ROOT.parents[1] / ".store/deepmuonreco/dataset/sim-phase2-d110-v001/test.h5"
PURPLE = "#7625df"
WP_COLORS = ("#55aaff", "#f49a38", "#e43d42")


def collect(data_h5, score_h5, records):
    """Keep only bin counts and per-event multiplicities in memory."""
    h, events = defaultdict(int), defaultdict(list)
    map_label = wp_label(0.999)
    for chunk in iter_scored_chunks(data_h5, score_h5):
        score, target, pt, eta, truth, lengths = (
            chunk[key] for key in ("score", "target", "pt", "eta", "truth", "lengths")
        )
        ml = {wp_label(r["tpr_requested"]): score > r["threshold"] for r in records}
        bases = {"signal": target, "background": ~target}
        if truth is not None:
            bases.update(truth=truth, nontruth=~truth)
        for name, base in bases.items():
            h["total", name] += int(base.sum())
            curves = ml if name in ("signal", "background") else {"CMS": target, **ml}
            for xmax in (10, 100):
                edges = np.linspace(0, xmax, 21)
                h["pt", name, "den", xmax] += np.histogram(pt[base], edges)[0]
                for label, cut in curves.items():
                    h["pt", name, label, xmax] += np.histogram(pt[base & cut], edges)[0]
            map_xmax = 10 if name in ("signal", "truth") else 20
            map_edges = (np.linspace(0, map_xmax, 81), np.linspace(-3, 3, 61))
            h["map", name, "den"] += np.histogram2d(pt[base], eta[base], map_edges)[0]
            for label in ((map_label,) if name in ("signal", "background")
                          else ("CMS", map_label)):
                h["map", name, label] += np.histogram2d(
                    pt[base & curves[label]], eta[base & curves[label]], map_edges
                )[0]
        for name, mask in (("signal", target), ("background", ~target)):
            h["roc", name] += np.histogram(score[mask], np.linspace(0, 1, 10_001))[0]
            h["score", name] += np.histogram(score[mask], np.linspace(0, 1, 21))[0]
            for label, cut in ml.items():
                h["pass", name, label] += int(np.count_nonzero(mask & cut))
        events["tracks"].append(lengths)
        events["signal"].append(event_counts(target, lengths))
        for label, cut in ml.items():
            events[label].append(event_counts(cut, lengths))
    return h, {name: np.concatenate(parts) for name, parts in events.items()}, map_label


def wp_label(target):
    return f"{100 * target:.1f}%"


def validation_points(test_h5, run):
    """Calibrate the slide's three working points on validation scores."""
    selected = []
    with h5py.File(test_h5.with_name("val.h5")) as data, \
            h5py.File(run / "predictions/val.h5") as prediction:
        scores = prediction["score"]
        if len(scores) != len(data["track_is_good_track"]):
            raise ValueError("Predictions cover only part of val.h5")
        for start in range(0, len(scores), 256):
            stop = min(start + 256, len(scores))
            masks = data["track_is_good_track"][start:stop]
            targets = data["track_is_trk_muon"][start:stop]
            block = scores[start:stop]
            selected.extend(score[target[np.asarray(mask, bool)].astype(bool)]
                            for mask, target, score in zip(masks, targets, block))
    signal = np.concatenate(selected)
    return [{"tpr_requested": target,
             "threshold": float(np.quantile(signal, 1 - target))}
            for target in (0.95, 0.99, 0.999)]


def ensure_predictions(model, test_h5):
    """Reuse scores for this H5 and checkpoint, or stream new predictions."""
    model = model.resolve()
    checkpoint = model if model.is_file() else model / "checkpoints/best.pt"
    run = checkpoint.parents[1]
    for split, source in (("val", test_h5.with_name("val.h5")), ("test", test_h5)):
        output = run / "predictions" / f"{split}.h5"
        ready = False
        if output.exists():
            with h5py.File(output) as scores, h5py.File(source) as data:
                ready = (scores.attrs.get("source_h5") == str(source.resolve())
                         and scores.attrs.get("checkpoint") == str(checkpoint.resolve())
                         and scores.attrs.get("precision") == "float32"
                         and len(scores["score"]) == len(data["track_is_good_track"])
                         and output.stat().st_mtime_ns >= max(
                             source.stat().st_mtime_ns, checkpoint.stat().st_mtime_ns))
        if not ready:
            subprocess.run(
                [str(MODEL_REPO / ".venv/bin/python"), "scripts/predict.py",
                 "-c", str(checkpoint), "-s", split,
                 f"paths.{split}_file={source.resolve()}", "torch.precision=float32"],
                cwd=MODEL_REPO, env={**os.environ, "PYTHONPATH": "src"}, check=True,
            )
    return run


def save(ax, name, output, com):
    hep.cms.label("Private Work", ax=ax, data=False, com=com,
                  fontsize=12 if name.endswith("_2d.png") else None)
    ax.figure.savefig(output / name, dpi=150, bbox_inches="tight")
    plt.close(ax.figure)
    print(output / name)


def roc_plots(h, labels, output, com, sample):
    s = h["roc", "signal"][::-1].cumsum()
    b = h["roc", "background"][::-1].cumsum()
    tpr = np.r_[0, s / s[-1]]
    fpr = np.r_[0, b / b[-1]]
    tnr = 1 - fpr
    auc = float(np.trapezoid(tpr, fpr))
    points = [(label, h["pass", "signal", label] / s[-1],
               1 - h["pass", "background", label] / b[-1]) for label in labels]

    _, ax = plt.subplots(figsize=(10, 8))
    ax.plot(fpr, tpr, color=PURPLE, lw=2.5, label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], "k:", lw=1)
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Background Acceptance",
           ylabel="Signal Efficiency")
    ax.legend(loc="lower right", title=sample)
    ax.grid(alpha=0.15)
    save(ax, "roc.png", output, com)

    _, ax = plt.subplots(figsize=(10, 8))
    ax.plot(tpr, tnr, color=PURPLE, lw=2.5, label=f"AUC = {auc:.3f}")
    for label, efficiency, rejection in points:
        ax.plot(efficiency, rejection, "ko", ms=6, label=label)
        ax.axvline(efficiency, color="0.6", ls=":", lw=1)
    lower = min(0.4, min(rejection for _, _, rejection in points) - 0.05)
    ax.set(xlim=(0.945, 1.001), ylim=(lower, 1), xlabel="Signal Efficiency",
           ylabel="Background Rejection")
    ax.legend(loc="lower left" if lower == 0.4 else "upper right", title="Working points")
    ax.grid(alpha=0.15)
    save(ax, "roc_zoom.png", output, com)

    _, ax = plt.subplots(figsize=(10, 8))
    x = 1 - tpr
    ax.plot(x[x > 0], tnr[x > 0], color=PURPLE, lw=2.5)
    for label, efficiency, rejection in points:
        if efficiency < 1:
            ax.plot(1 - efficiency, rejection, "ko", ms=6, label=label)
            ax.axvline(1 - efficiency, color="0.6", ls=":", lw=1)
    ax.set_xscale("log")
    ax.set(xlim=(1, 1e-6), ylim=(0, 1), xlabel="Signal Rejection",
           ylabel="Background Rejection")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="lower left", title=sample)
    ax.grid(alpha=0.15)
    save(ax, "roc_log.png", output, com)
    return auc


def score_plot(h, output, com, sample):
    edges = np.linspace(0, 1, 21)
    centres = (edges[1:] + edges[:-1]) / 2
    _, ax = plt.subplots(figsize=(10, 8))
    for name, label, color in (("signal", "Signal", "#e43d42"),
                               ("background", "Background", "#55aaff")):
        counts = h["score", name]
        scale = counts.sum() * np.diff(edges)
        ax.stairs(counts / scale, edges, color=color, lw=2, label=label)
        ax.errorbar(centres, counts / scale, yerr=np.sqrt(counts) / scale,
                    fmt="none", color=color, lw=1)
    ax.set(xlim=(0, 1), ylim=(0, 14.5), xlabel="Score", ylabel="Normalized")
    ax.legend(loc="upper center", title=sample)
    ax.grid(alpha=0.15)
    save(ax, "score.png", output, com)


def binomial_rate(num, den, complement):
    """One-sigma Wilson interval, including bins with zero successes."""
    valid = den > 0
    n, d = num[valid], den[valid]
    p = n / d
    mid = (p + 0.5 / d) / (1 + 1 / d)
    half = np.sqrt(p * (1 - p) / d + 0.25 / d**2) / (1 + 1 / d)
    low, high = np.maximum(0, mid - half), np.minimum(1, mid + half)
    if complement:
        return valid, 1 - p, np.maximum(0, [high - p, p - low])
    return valid, p, np.maximum(0, [p - low, high - p])


def pt_plot(h, base, curves, xmax, ylabel, invert, output, name, com, ymin=0):
    edges = np.linspace(0, xmax, 21)
    centres = (edges[1:] + edges[:-1]) / 2
    den = h["pt", base, "den", xmax]
    _, ax = plt.subplots(figsize=(10, 8))
    for label, color, marker in curves:
        num = h["pt", base, label, xmax]
        valid, rate, errors = binomial_rate(num, den, invert)
        ax.errorbar(centres[valid], rate, xerr=(edges[1] - edges[0]) / 2,
                    yerr=errors, fmt=marker, color=color, ms=5, lw=1,
                    capsize=1, label="TrackerMuon" if label == "CMS"
                    else rf"$\epsilon_{{\mathrm{{sig}}}}$={label}")
    ax.set(xlim=(0, xmax), ylim=(ymin, 1.02), xlabel=r"Tracker Track $p_T$ [GeV]",
           ylabel=ylabel)
    ax.legend(loc="upper right" if invert else "lower right")
    ax.grid(alpha=0.15)
    save(ax, name, output, com)


def color_scale(ax, cmap, label):
    """Draw a 0-1 color scale inside the data Axes, without a second Axes."""
    for i in range(80):
        ax.add_patch(Rectangle((1.04, i / 80), 0.035, 1 / 80,
                               transform=ax.transAxes, clip_on=False,
                               facecolor=cmap(i / 79), edgecolor="none"))
    for value in (0, 0.5, 1):
        ax.text(1.09, value, f"{value:.1f}", va="center",
                transform=ax.transAxes, fontsize=16)
    ax.text(1.18, 0.5, label, rotation=90, va="center",
            transform=ax.transAxes, fontsize=17)


def map_plot(h, base, selected, xmax, label, output, name, com, invert=False):
    pt_edges = np.linspace(0, xmax, 81)
    eta_edges = np.linspace(-3, 3, 61)
    den = h["map", base, "den"]
    num = h["map", base, selected]
    rate = np.divide(num, den, out=np.full_like(den, np.nan), where=den > 0)
    if invert:
        rate = 1 - rate
    cmap = plt.get_cmap("plasma" if invert or label == "Fake Rate" else "viridis").copy()
    cmap.set_bad("white")
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.pcolormesh(pt_edges, eta_edges, np.ma.masked_invalid(rate.T),
                  cmap=cmap, vmin=0, vmax=1, shading="auto")
    ax.set(xlim=(0, xmax), ylim=(-3, 3), xlabel=r"Tracker Track $p_T$ [GeV]",
           ylabel=r"Tracker Track $\eta$")
    color_scale(ax, cmap, label)
    fig.subplots_adjust(left=0.12, right=0.76, bottom=0.12, top=0.88)
    save(ax, name, output, com)


def event_counts(mask, lengths):
    ends = np.r_[0, lengths.cumsum()]
    return np.array([np.count_nonzero(mask[a:b]) for a, b in zip(ends[:-1], ends[1:])])


def event_plot(events, labels, output, com, sample, phase2):
    items = [("Tracker Tracks (S+B)", events["tracks"], "#55aaff")]
    items += [(f"ML {label}", events[label], color)
              for label, color in zip(labels[::-1], ("0.55", "#a83ca8", "#f49a38"))]
    items += [("Tracker Muons (S)", events["signal"], "#e43d42")]
    xmax = 2500 if phase2 else 600
    _, ax = plt.subplots(figsize=(10, 8))
    for label, counts, color in items:
        ax.hist(counts, bins=20, range=(0, xmax), histtype="step", density=True,
                color=color, lw=2, label=rf"{label}; $\langle N\rangle$={counts.mean():.1f}")
    ax.set(xlim=(0, xmax), ylim=(0, 0.01 if phase2 else 0.04), xlabel="Number of Objects",
           ylabel="Normalized")
    ax.legend(loc="upper right", title=sample, fontsize=14)
    ax.grid(alpha=0.15)
    save(ax, "event_summary.png", output, com)


def plot_run(run, test_h5):
    score_h5 = run / "predictions/test.h5"
    with h5py.File(test_h5) as data, h5py.File(score_h5) as scores:
        if len(data["track_is_good_track"]) != len(scores["score"]):
            raise ValueError("Predictions cover only part of test.h5; run predict.py on the full split")
    output = ROOT / "plots" / run.name
    output.mkdir(parents=True, exist_ok=True)
    phase2 = "phase2" in str(test_h5).lower()
    com = 14.0 if phase2 else 13.6
    sample = r"$\mu^+\mu^- + 200\mathrm{PU}$" if phase2 else r"$\mu^+\mu^- + $ Run 3 PU"

    records = validation_points(test_h5, run)
    h, events, map_label = collect(test_h5, score_h5, records)
    labels = [wp_label(r["tpr_requested"]) for r in records]
    ml_curves = [(label, color, "o")
                 for label, color in zip(labels, WP_COLORS)]

    auc = roc_plots(h, labels, output, com, sample)
    score_plot(h, output, com, sample)
    for xmax, suffix in ((100, "full"), (10, "low")):
        pt_plot(h, "signal", ml_curves, xmax, "Efficiency", False,
                output, f"eff_pt_{suffix}.png", com, ymin=0.8)
        pt_plot(h, "background", ml_curves, xmax, "Background Rejection", True,
                output, f"rej_pt_{suffix}.png", com)
    map_plot(h, "signal", map_label, 10, f"Signal Efficiency (ML {map_label})",
             output, "signal_eff_2d.png", com)
    map_plot(h, "background", map_label, 20, f"Background Rejection (ML {map_label})",
             output, "bkg_rej_2d.png", com, invert=True)
    event_plot(events, labels, output, com, sample, phase2)

    if ("total", "truth") in h:
        truth_curves = [("CMS", "#a83ca8", "s"), *ml_curves]
        for xmax, suffix in ((100, "full"), (10, "low")):
            pt_plot(h, "truth", truth_curves, xmax, "Truth Muon Efficiency", False,
                    output, f"truth_eff_pt_{suffix}.png", com)
            pt_plot(h, "nontruth", truth_curves, xmax, "Fake Rate", False,
                    output, f"fake_rate_pt_{suffix}.png", com)
        for base, title, xmax, stem in (("truth", "Truth Muon Efficiency", 10, "truth_eff"),
                                        ("nontruth", "Fake Rate", 20, "fake_rate")):
            map_plot(h, base, "CMS", xmax, title, output, f"{stem}_cms_2d.png", com)
            map_plot(h, base, map_label, xmax, title, output, f"{stem}_ml_2d.png", com)

    summary = {
        "run": str(run), "test_h5": str(test_h5), "events": len(events["tracks"]),
        "good_tracks": int(h["total", "signal"] + h["total", "background"]),
        "tracker_muons": int(h["total", "signal"]), "auroc": auc,
        "working_points": [
            {**record, "test_efficiency": h["pass", "signal", label] / h["total", "signal"],
             "test_rejection": 1 - h["pass", "background", label] / h["total", "background"]}
            for record, label in zip(records, labels)
        ],
    }
    (output / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(output / "metrics.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5", type=Path, default=TEST)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    test_h5 = args.h5.resolve()
    plot_run(ensure_predictions(args.model, test_h5), test_h5)


if __name__ == "__main__":
    main()
