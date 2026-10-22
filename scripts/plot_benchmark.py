"""Draw Muon ID timing ratios, time distributions and a module-time sunburst."""

import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import mplhep as hep
import numpy as np


plt.style.use(hep.style.CMS)
ROOT = Path(__file__).resolve().parents[1]
MODES = ("baseline", "cpu_filter", "gpu_filter")
COLORS = {"cpu": "#f49a38", "gpu": "#55aaff"}
EVENT_REPORT = re.compile(
    r"Begin processing the (\d+)(?:st|nd|rd|th) record\. Run (\d+), Event (\d+), "
    r"LumiSection (\d+) on stream (\d+)"
)
TIMING_LINE = re.compile(
    r"FastReport\s+(\S+) ms\s+(\S+) ms\s+[+-]?\d+ kB\s+[+-]?\d+ kB\s+(.+?)\s*$"
)


def read_timing(path, mode):
    """Pair each FwkReport event ID with its following single-stream timer block."""
    events, pending, current = {}, None, None
    for line in path.read_text().splitlines():
        report = EVENT_REPORT.search(line)
        if report:
            ordinal, run, event, lumi, stream = map(int, report.groups())
            if stream != 0 or ordinal != len(events) + 1 or pending is not None:
                raise ValueError(f"{mode}: require every-event FwkReport and one stream")
            pending = (run, lumi, event)
            if pending in events:
                raise ValueError(f"{mode}: duplicate event identity {pending}")
        elif re.match(r"FastReport\s+-+ Event Summary -+", line):
            if pending is None or current is not None:
                raise ValueError(f"{mode}: event timing has no unique preceding FwkReport")
            current = {}
        elif current is not None and line.rstrip().endswith("Processes and Paths"):
            required = {"total", "muons1stStep"}
            if mode != "baseline":
                required.add("muonIdONNX")
            if set(current) != required:
                raise ValueError(f"{mode}: missing or unexpected timed modules: {current}")
            if not all(np.isfinite(value) and value >= 0 for value in current.values()) or current["total"] <= 0:
                raise ValueError(f"{mode}: invalid event timing")
            events[pending] = current
            pending, current = None, None
        elif current is not None:
            match = TIMING_LINE.fullmatch(line)
            if match and match[3] in ("total", "muons1stStep", "muonIdONNX"):
                if match[3] in current:
                    raise ValueError(f"{mode}: duplicate module in an event timing block")
                current[match[3]] = float(match[2])
    if pending is not None or current is not None or not events:
        raise ValueError(f"{mode}: incomplete or missing native event reports")
    return events


def read_runs(directory):
    """Require completed baseline, CPU-filter and GPU-filter runs of the same events."""
    runs, settings = {}, {}
    for mode in MODES:
        folder = directory / mode
        settings[mode] = dict(line.split("=", 1) for line in
                              (folder / "settings.txt").read_text().splitlines())
        expected_backend = "none" if mode == "baseline" else ("cuda" if mode.startswith("gpu_") else "cpu")
        if settings[mode].get("mode") != mode or settings[mode].get("backend") != expected_backend:
            raise ValueError(f"{mode}: recorded case or backend does not match its directory")
        events = read_timing(folder / "run.log", mode)
        summary = json.loads((folder / "resources.json").read_text())
        completed = summary["total"]["events"]
        requested = int(settings[mode]["maxEvents"])
        if len(events) != completed or (requested > 0 and completed != requested):
            raise ValueError(f"{mode}: requested, native and completed event counts disagree")
        modules = {module["label"]: module for module in summary["modules"]}
        if modules.get("recoProducts", {}).get("events") != completed:
            raise ValueError(f"{mode}: full reconstruction products were not consumed on all events")
        labels = ["muons1stStep"] + ([] if mode == "baseline" else ["muonIdONNX"])
        for label in labels:
            module = modules.get(label)
            if module is None or module["events"] != completed:
                raise ValueError(f"{mode}: {label} did not run on all events")
            # The native per-event report rounds to 0.1 ms; JSON retains precision.
            reported = sum(event[label] for event in events.values())
            if abs(reported - module["time_real"]) > 0.051 * completed:
                raise ValueError(f"{mode}: native and JSON module times disagree for {label}")
        reported = sum(event["total"] for event in events.values())
        processing = sum(module["time_real"] for module in summary["modules"]
                         if module["type"] not in ("eventsetup", "other", "idle"))
        if abs(reported - processing) > 0.051 * completed:
            raise ValueError(f"{mode}: native and JSON event totals disagree")
        runs[mode] = {
            "modules": summary["modules"],
            "event_ms": {key: row["total"] for key, row in events.items()},
            "muon_ms": {key: row["muons1stStep"] for key, row in events.items()},
            "onnx_ms": {key: row.get("muonIdONNX", 0.0) for key, row in events.items()},
            "chain_ms": {key: row["muons1stStep"] + row.get("muonIdONNX", 0.0)
                         for key, row in events.items()},
        }
    for name in ("input", "maxEvents", "threshold"):
        values = {setting.get(name) for setting in settings.values()}
        if len(values) != 1 or None in values or "" in values:
            raise ValueError(f"Run settings differ or are missing: {name}")
    hashes = {settings[mode].get("modelSHA256") for mode in MODES[1:]}
    if len(hashes) != 1 or None in hashes or "" in hashes:
        raise ValueError("All ONNX runs must use the same recorded model")
    keys = set(runs["baseline"]["event_ms"])
    if any(set(run["event_ms"]) != keys for run in runs.values()):
        raise ValueError("Event identities differ between cases")
    threshold = float(settings["cpu_filter"]["threshold"])
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("The threshold must be a probability between 0 and 1")
    return runs, threshold



def working_point(threshold):
    if np.isclose(threshold, 0.38735, rtol=0, atol=1e-8):
        return r"$\epsilon_{\mathrm{signal}} = 99.9\%$"
    return f"Threshold = {threshold:g}"


def save(ax, output, name, right_ax=None):
    sunburst = name == "timing_sunburst"
    hep.cms.label("Private Work", ax=ax, data=False, com=14,
                  rlabel="" if right_ax is not None or sunburst else None,
                  fontsize=20 if right_ax is not None else 24)
    if right_ax is not None:
        hep.label.lumitext("(14 TeV)", ax=right_ax, fontsize=20)
    if sunburst:
        ax.figure.text(0.98, ax.get_position().y1 + 0.01, "(14 TeV)",
                       ha="right", va="bottom", fontsize=24)
    filename = output / f"{name}.png"
    ax.figure.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close(ax.figure)
    print(filename)


def timing_plot(runs, threshold, output):
    keys = sorted(runs["baseline"]["muon_ms"])
    baseline = np.array([runs["baseline"]["muon_ms"][key] for key in keys])
    if np.any(baseline <= 0):
        raise ValueError("Baseline Muon ID time must be positive for event-paired ratios")
    _, ax = plt.subplots(figsize=(10, 8))
    ratios = []
    ax.axhline(1, color="0.6", ls="--", lw=1)
    for device, marker in (("cpu", "o"), ("gpu", "s")):
        values = np.array([runs[device + "_filter"]["chain_ms"][key] for key in keys]) / baseline
        ratios.extend(values)
        ax.scatter(baseline, values, s=18, marker=marker, color=COLORS[device],
                   edgecolors="none", alpha=0.65, label=device.upper())
    ax.set(xlim=(baseline.min() * 0.9, baseline.max() * 1.05), ylim=(0, max(1, max(ratios)) * 1.2),
           xlabel="Baseline [ms]", ylabel="Filtered / Baseline")
    ax.text(0.04, 0.95, f"Events: {len(keys):,}\n{working_point(threshold)}",
            transform=ax.transAxes, va="top", fontsize=19)
    ax.legend(loc="lower right", fontsize=21, markerscale=1.7,
              title="Filtered = MuonIdProducer + ONNX", title_fontsize=12)
    ax.grid(alpha=0.2, ls=":")
    save(ax, output, "paired_timing")


def distribution_plot(runs, threshold, output):
    keys = sorted(runs["baseline"]["muon_ms"])
    times = {mode: np.array([runs[mode]["chain_ms"][key] for key in keys]) for mode in MODES}
    baseline = times["baseline"]
    maximum = max(values.max() for values in times.values())
    bins = np.linspace(0, maximum * 1.1, 21)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharex=True, sharey=True)
    fig.subplots_adjust(wspace=0.08)
    peak = 0
    for device, ax in zip(("cpu", "gpu"), axes):
        run = runs[device + "_filter"]
        muon_mean = np.mean([run["muon_ms"][key] for key in keys])
        onnx_mean = np.mean([run["onnx_ms"][key] for key in keys])
        curves = ((f"MuonIdProducer\n({baseline.mean():.1f} ms)", baseline, "#55aaff"),
                  (f"MuonIdProducer + ONNX\n({muon_mean:.1f} + {onnx_mean:.1f} ms)",
                   times[device + "_filter"], "#8a8a8a"))
        for label, values, color in curves:
            counts, _, _ = ax.hist(values, bins=bins, histtype="step", lw=2, color=color, label=label)
            peak = max(peak, counts.max())
        ax.set(xlabel="Time [ms]", xlim=(bins[0], bins[-1]))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.text(0.04, 0.95, device.upper(), transform=ax.transAxes, va="top", fontsize=21, fontweight="bold")
        ax.text(0.04, 0.84, f"Events: {len(keys):,}\n{working_point(threshold)}",
                transform=ax.transAxes, va="top", fontsize=14)
        ax.legend(loc="upper right", fontsize=13)
        ax.grid(alpha=0.2, ls=":")
    axes[0].set(ylabel="Events", ylim=(0, max(peak, 1) * 1.5))
    save(axes[0], output, "timing_distribution", right_ax=axes[1])


GROUPS = {
    "Tracking": ("#55aaff", ("RecoTracker", "RecoLocalTracker", "RecoPixelVertexing", "TrackingTools")),
    "Calorimetry": ("#f49a38", ("RecoLocalCalo", "RecoHGCal", "RecoEcal")),
    "Muons": ("#e43d42", ("RecoMuon", "RecoLocalMuon")),
    "Particle flow": ("#2ca089", ("RecoParticleFlow", "ParticleFlow")),
    "Egamma": ("#d6bc36", ("RecoEgamma",)),
    "Vertices / timing": ("#8c6bb1", ("RecoVertex", "RecoMTD", "RecoLocalFastTime")),
    "I/O": ("#808080", ("I/O",)),
    "Other reco": ("#b8b8b8", ()),
    "Unclassified": ("#a48061", ()),
}


def group_modules(modules):
    """Use the pinned CMS Circles Phase-II label-to-package table; retain unknowns."""
    packages = json.loads((ROOT / "data/benchmark_groups.json").read_text())
    packages["muonIdONNX"] = "RecoMuon|MuonIdentification"
    wildcards = [(pattern, package) for pattern, package in packages.items() if "*" in pattern]
    grouped = {}
    for module in modules:
        if not module["label"] or module["time_real"] <= 0 or module["type"] in (
            "eventsetup", "other", "idle", "PathStatusInserter", "TriggerResultInserter",
            "AsciiOutputModule", "PoolOutputModule",
        ):
            continue
        label = module["label"].split("@", 1)[0]
        package = packages.get(label)
        if package is None:
            package = next((value for pattern, value in wildcards if fnmatchcase(label, pattern)), None)
        group = "Unclassified" if package is None else "Other reco"
        for name, (_, prefixes) in GROUPS.items():
            if package is not None and package.split("|", 1)[0] in prefixes:
                group = name
                break
        grouped.setdefault(group, []).append((module["label"], module["time_real"]))
    return grouped


def sunburst_plot(runs, threshold, output):
    run = runs["gpu_filter"]
    groups = group_modules(run["modules"])
    groups = sorted(groups.items(), key=lambda item: -sum(value for _, value in item[1]))
    totals = [sum(value for _, value in members) for _, members in groups]
    total = sum(totals)
    if not np.isfinite(total) or total <= 0:
        raise ValueError("No valid module resources for the sunburst")
    targets = {"muons1stStep", "muonIdONNX"}
    leaves, values, colors = [], [], []
    for group, members in groups:
        selected = [(label, value) for label, value in members if value >= 0.03 * total or label in targets]
        selected.sort(key=lambda item: -item[1])
        remainder = sum(value for _, value in members) - sum(value for _, value in selected)
        if remainder > 1e-8:
            selected.append(("Other", remainder))
        for index, (label, value) in enumerate(selected):
            leaves.append(label)
            values.append(value)
            color = np.array(matplotlib.colors.to_rgb(GROUPS[group][0]))
            colors.append(color + (1 - color) * (0.15 * (index % 3)))
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.subplots_adjust(right=0.73, bottom=0.15)
    inner, _ = ax.pie(totals, radius=0.78, colors=[GROUPS[name][0] for name, _ in groups],
                      startangle=90, counterclock=False, wedgeprops=dict(width=0.33, edgecolor="white"))
    outer, _ = ax.pie(values, radius=1.1, colors=colors, startangle=90, counterclock=False,
                      wedgeprops=dict(width=0.31, edgecolor="white"))
    for wedge, (name, _), value in zip(inner, groups, totals):
        if value < 0.1 * total:
            continue
        angle = np.deg2rad((wedge.theta1 + wedge.theta2) / 2)
        ax.text(0.61 * np.cos(angle), 0.61 * np.sin(angle), name.replace(" / ", "/\n"),
                ha="center", va="center", fontsize=14)
    for wedge, label, value in zip(outer, leaves, values):
        if label == "Other" or (value < 0.03 * total and label != "muons1stStep"):
            continue
        angle = (wedge.theta1 + wedge.theta2) / 2
        text = re.sub(r"(TrackCandidates|HitQuadruplets|HitTriplets|LayerClusters|WithMTD|Tracks|Seeds)$", r"\n\1", label)
        rotation = angle + (180 if 90 < angle % 360 < 270 else 0)
        ax.text(0.95 * np.cos(np.deg2rad(angle)), 0.95 * np.sin(np.deg2rad(angle)), text,
                ha="center", va="center", rotation=rotation, fontsize=9)
    mean_seconds = total / len(run["event_ms"]) / 1000
    ax.text(0, 0, f"GPU filter\n{mean_seconds:.2f} s/event\nModule-time sum", ha="center", va="center", fontsize=17)
    handles = [Patch(facecolor=GROUPS[name][0], label=f"{name}: {100 * value / total:.1f}%")
               for (name, _), value in zip(groups, totals)]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=15)
    ax.text(0.5, -0.08, f"Events: {len(run['event_ms']):,}; {working_point(threshold)}\n"
            "Σ module wall times incl. I/O; inner = subsystem, outer = module",
            transform=ax.transAxes, ha="center", va="top", fontsize=12)
    save(ax, output, "timing_sunburst")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "output/benchmark")
    parser.add_argument("--output", type=Path, default=ROOT / "output/plots/benchmark/baseline-01")
    args = parser.parse_args()
    try:
        runs, threshold = read_runs(args.input)
        args.output.mkdir(parents=True, exist_ok=True)
        timing_plot(runs, threshold, args.output)
        distribution_plot(runs, threshold, args.output)
        sunburst_plot(runs, threshold, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    for obsolete in ("onnx_timing.png", "muon_retention_pt.png"):
        (args.output / obsolete).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
