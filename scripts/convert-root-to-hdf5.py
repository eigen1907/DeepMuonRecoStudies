#!/usr/bin/env python
import argparse
import uproot
from pathlib import Path
import h5py as h5
import numpy as np


def prepare_for_hdf5(value: np.ndarray) -> np.ndarray:
    """Normalize uproot arrays for HDF5 writes.

    Uproot may return a jagged branch as a regular 2D array when every event in
    a batch has the same multiplicity, including the all-empty shape (N, 0).
    Store those branches as 1D variable-length arrays so later batches with
    different multiplicities append cleanly.
    """

    if value.ndim > 1:
        dtype = np.float32 if value.dtype == np.float64 else value.dtype
        output = np.empty(value.shape[0], dtype=object)
        for i, each in enumerate(value):
            output[i] = np.asarray(each, dtype=dtype)
        return output

    if value.dtype == object and len(value) > 0 and isinstance(value[0], np.ndarray):
        dtype = np.float32 if value[0].dtype == np.float64 else value[0].dtype
        output = np.empty(len(value), dtype=object)
        for i, each in enumerate(value):
            output[i] = np.asarray(each, dtype=dtype)
        return output

    return value


def hdf5_dtype(value: np.ndarray) -> np.dtype | h5.Datatype:
    if value.dtype != object:
        return value.dtype

    for each in value:
        if isinstance(each, np.ndarray):
            return h5.vlen_dtype(each.dtype)

    raise ValueError("Cannot infer HDF5 dtype from an empty object array.")


def append_dataset(output_file: h5.File, key: str, value: np.ndarray) -> None:
    if key not in output_file:
        output_file.create_dataset(
            name=key,
            data=value,
            maxshape=(None,),
            chunks=True,
            dtype=hdf5_dtype(value),
        )
        return

    dset = output_file[key]
    start = dset.shape[0]
    dset.resize((start + value.shape[0]), axis=0)
    try:
        dset[start:] = value
    except TypeError:
        if value.dtype != object:
            raise
        for i, each in enumerate(value):
            dset[start + i] = each


def convert(input_file_path: Path, treepath: str, step_size: str = "4 GB"):
    if not input_file_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file_path}")
    print(f"Converting {input_file_path} to HDF5 format (Batch mode)...")

    output_file_path = input_file_path.with_suffix(".h5")
    if output_file_path.exists():
        raise FileExistsError(f"Output file already exists: {output_file_path}")
    print(f"Output file will be: {output_file_path}")

    with h5.File(output_file_path, "w") as output_file:
        iterator = uproot.iterate(
            f"{input_file_path}:{treepath}", step_size=step_size, library="np"
        )

        for i, batch in enumerate(iterator):
            print(f"Processing batch {i + 1}...")

            for key, value in batch.items():
                append_dataset(output_file, key, prepare_for_hdf5(value))

    print("Conversion complete.")


def run(input_file_path_list: list[Path], treepath: str, step_size: str):
    for input_file_path in input_file_path_list:
        convert(input_file_path, treepath, step_size)


def main():
    parser = argparse.ArgumentParser(description="Convert ROOT file to HDF5 format.")
    parser.add_argument(
        "-i",
        "--input",
        dest="input_file_path_list",
        type=Path,
        nargs="+",
        help="Path to the input ROOT file.",
    )
    parser.add_argument(
        "--treepath",
        type=str,
        default="deepMuonRecoNtuplizer/tree",
        help="Path to the tree inside the ROOT file.",
    )
    parser.add_argument(
        "--step-size", type=str, default="4 GB", help="Batch size for processing."
    )
    args = parser.parse_args()

    run(**vars(args))


if __name__ == "__main__":
    main()
