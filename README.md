# DeepMuonRecoStudies

Plotting, validation, and exploratory studies for the DeepMuonReco project.

## Related repositories

- `DeepMuonRecoSample`: CMSSW sample and ntuple production
- `DeepMuonReco`: model training, evaluation, and ONNX export
- `DeepMuonRecoStudies`: plotting, validation, and analysis studies

## Structure

```text
DeepMuonRecoStudies/
├── logs/        # logs
├── notebooks/   # exploratory studies
├── plots/       # generated and selected plots
├── scripts/     # reuseable scripts
├── pyproject.toml
├── uv.lock
└── README.md
```

## Setup

Dependencies are managed with `uv`.

```bash
uv sync
```

Run Python scripts with:

```bash
uv run python <script.py>
```

## Jupyter on VS Code Server

Register the project virtual environment as a Jupyter kernel:

```bash
uv run python -m ipykernel install \
    --user \
    --name deepmuonreco-studies \
    --display-name "Python (DeepMuonRecoStudies)"
```

Then reload VS Code and select `Python (DeepMuonRecoStudies)` as the notebook kernel.