import argparse
import logging
from pathlib import Path
from contextlib import nullcontext
import warnings

import h5py as h5
import numpy as np
import torch
from torch.utils.data import DataLoader

from tensordict.nn import TensorDictModule

from hydra.utils import instantiate
from omegaconf import OmegaConf
from omegaconf import DictConfig

import tqdm.rich
from tqdm import TqdmExperimentalWarning
from rich.logging import RichHandler
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from muonly.data.datasets import TrackerTrackSelectionDataset
from muonly.data.utils import configure_model_in_keys
from muonly.data.transforms.utils import configure_preprocessing

_logger = logging.getLogger(Path(__file__).name)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)

warnings.filterwarnings("ignore", category=TqdmExperimentalWarning)

CHUNK_EVENTS = 256


def extend_hdf5_dataset(dataset: h5.Dataset, new_data: np.ndarray) -> None:
    """Extend an HDF5 dataset with new data."""
    new_size = dataset.shape[0] + len(new_data)
    dataset.resize((new_size,))
    dataset[-len(new_data) :] = new_data


def run(
    ckpt_path: Path,
    split: str,
    args_list: list[str],
) -> None:
    """ """
    run_dir = ckpt_path.parents[1]
    base_config = OmegaConf.load(run_dir / "config.yaml")
    cli_config = OmegaConf.from_cli(args_list)
    config = OmegaConf.merge(base_config, cli_config)
    if not isinstance(config, DictConfig):
        raise ValueError("Expected config to be a DictConfig")

    output_dir = Path(config.paths.get("prediction_dir", run_dir / "predictions"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{split}.h5"

    device = torch.device(config.torch.device)
    _logger.info(f"{device=}")

    # ---------------------------------------------------------------------------
    # Model
    # ---------------------------------------------------------------------------
    model = instantiate(config.model)
    checkpoint = torch.load(ckpt_path, map_location="cpu")
    model.load_state_dict(checkpoint["model"])
    del checkpoint

    model = model.to(device)
    model = model.eval()
    _logger.info(f"Loaded checkpoint from {ckpt_path}")

    td_model = TensorDictModule(
        module=model,
        in_keys=configure_model_in_keys(config=config),
        out_keys=["logits"],
    )

    input_path = Path(config.paths[f"{split}_file"])
    with h5.File(input_path, "r") as input_file:
        total_events = len(next(iter(input_file.values())))
    limit = TrackerTrackSelectionDataset._get_stop(
        max_events=config.data_load[f"{split}_max_events"], total=total_events
    )
    num_events = total_events if limit is None else limit
    _logger.info(f"Number of {split} examples: {num_events}")
    preprocessing = configure_preprocessing(config.data)

    # --------------------------------------------------------------------------
    # Mixed precision (mirror training)
    # --------------------------------------------------------------------------
    if config.torch.precision == "bfloat16":
        amp_context = torch.autocast(device_type=device.type, dtype=torch.bfloat16)
    else:
        amp_context = nullcontext()

    # --------------------------------------------------------------------------
    # output file
    # --------------------------------------------------------------------------
    partial_path = output_path.with_name(f"{split}.partial.h5")
    with h5.File(partial_path, "w") as output_file:
        output_file.attrs["source_h5"] = str(input_path.resolve())
        output_file.attrs["checkpoint"] = str(ckpt_path.resolve())
        output_file.attrs["precision"] = str(config.torch.precision)
        scores = output_file.create_dataset(
            name="score",
            shape=(0,),
            maxshape=(None,),
            dtype=h5.vlen_dtype(np.float32),
        )

        for start in tqdm.rich.tqdm(
            range(0, num_events, CHUNK_EVENTS), desc="Predicting event chunks"
        ):
            dataset = TrackerTrackSelectionDataset(
                path=input_path,
                config=config.data,
                max_events=min(CHUNK_EVENTS, num_events - start),
                start_event=start,
            )
            dataset.apply_(preprocessing)
            loader = DataLoader(
                dataset=dataset,
                batch_size=config.data_load.eval_batch_size,
                shuffle=False,
                num_workers=config.data_load.num_workers,
                collate_fn=dataset.collate,
            )

            for batch in loader:
                batch = batch.to(device)
                with amp_context:
                    batch = td_model(batch)

                mask_batch = batch["tracker_track_data_mask"].bool().cpu().numpy()
                score_batch = batch["logits"].sigmoid().float().cpu().numpy()
                score_batch = np.array(
                    [score[mask] for mask, score in zip(mask_batch, score_batch)],
                    dtype=object,
                )
                extend_hdf5_dataset(scores, score_batch)

            del loader, dataset, batch

    partial_path.replace(output_path)
    _logger.info(f"Saved predictions to {output_path}")


@torch.inference_mode()
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save model predictions to an HDF5 file.",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--ckpt",
        dest="ckpt_path",
        type=Path,
        help="Path to the model checkpoint (e.g., 'runs/exp1/checkpoints/best.ckpt')",
    )
    parser.add_argument(
        "-s",
        "--split",
        dest="split",
        type=str,
        choices=["train", "val", "test"],
        default="test",
        help="Which data split to predict on (e.g., 'test')",
    )
    args, unknown_args = parser.parse_known_args()

    run(**vars(args), args_list=unknown_args)


if __name__ == "__main__":
    main()
