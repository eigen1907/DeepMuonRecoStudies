"""Stream good tracks and their model scores from matching H5 event ranges."""

from pathlib import Path

import h5py
import numpy as np


BRANCHES = {
    "target": "track_is_trk_muon",
    "truth": "track_is_matched_muon",
    "pt": "track_pt",
    "eta": "track_eta",
}


def iter_scored_chunks(data_path: str | Path, score_path: str | Path):
    """Yield flat selected-track arrays plus their per-event lengths."""
    with h5py.File(data_path) as data, h5py.File(score_path) as prediction:
        branches = {name: data[key] for name, key in BRANCHES.items()}
        for start in range(0, len(prediction["score"]), 64):
            stop = min(start + 64, len(prediction["score"]))
            masks = data["track_is_good_track"][start:stop]
            scores = prediction["score"][start:stop]
            values = {name: branch[start:stop] for name, branch in branches.items()}
            selected = {name: [] for name in BRANCHES}
            for i, (raw_mask, score) in enumerate(zip(masks, scores)):
                mask = np.asarray(raw_mask, dtype=bool)
                if len(score) != mask.sum():
                    raise ValueError(f"Event {start + i}: score count differs from good tracks")
                for name, block in values.items():
                    selected[name].append(block[i][mask])

            chunk = {name: np.concatenate(parts) for name, parts in selected.items()}
            chunk["score"] = np.concatenate(scores)
            chunk["lengths"] = np.array([len(score) for score in scores])
            chunk["target"] = chunk["target"].astype(bool)
            chunk["truth"] = (None if np.all(chunk["truth"] == -1)
                              else chunk["truth"].astype(bool))
            yield chunk
