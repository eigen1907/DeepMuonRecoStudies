"""Compare PyTorch and ONNX, and save three events for the CMSSW check."""

import numpy as np
import onnx
import onnxruntime as ort
import torch

from muonly.data.datasets import TrackerTrackSelectionDataset
from export_onnx import INPUT_NAMES, OUTPUT, ROOT, load_model


DATA = ROOT / "output/dataset/sim-phase2-d110-v001/test.h5"


@torch.inference_mode()
def main():
    torch.set_num_threads(1)
    wrapper, config = load_model()
    model_path = OUTPUT / "model.onnx"
    graph = onnx.load(model_path)
    onnx.checker.check_model(graph)
    assert graph.ir_version <= 8, "CMSSW ONNXRuntime 1.14 requires ONNX IR <= 8"
    dataset = TrackerTrackSelectionDataset(DATA, config.data, max_events=3)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model_path), options,
                                   providers=["CPUExecutionProvider"])
    validation = ROOT / "output/plots/onnx/phase2-d110/baseline-01"
    validation.mkdir(parents=True, exist_ok=True)
    with (validation / "events.txt").open("w") as fixture:
        fixture.write(f"{len(dataset)}\n")
        for index, event in enumerate(dataset):
            batch = dataset.collate([event])
            inputs = tuple(batch[name].float() for name in INPUT_NAMES)
            expected = wrapper(*inputs).numpy()
            actual = session.run(["logits"], dict(zip(INPUT_NAMES, [x.numpy() for x in inputs])))[0]
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-4)
            counts = [x.shape[1] for x in inputs[::2]]
            fixture.write(" ".join(map(str, counts)) + "\n")
            for values in (*inputs[::2], expected):
                np.savetxt(fixture, np.asarray(values).reshape(1, -1), fmt="%.9g")
            print(f"event {index}: counts={counts}, max |PyTorch - ONNX|={np.max(np.abs(actual - expected)):.3g}")
    print(f"Wrote {validation / 'events.txt'}")


if __name__ == "__main__":
    main()
