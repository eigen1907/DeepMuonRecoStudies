"""Export baseline-01 with its preprocessing as a single ONNX model."""

from pathlib import Path

import torch
from hydra.utils import instantiate
from omegaconf import OmegaConf

from muonly.utils.onnx import Phase2NoHitModelWrapper


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output/model/phase2-d110/baseline-01"
OUTPUT = ROOT / "output/onnx/phase2-d110/baseline-01"
OBJECTS = ("tracker_track", "dt_segment", "csc_segment", "gem_segment")
INPUT_NAMES = [key for name in OBJECTS for key in (name, f"{name}_data_mask")]


class TrackLog(torch.nn.Module):
    """Equivalent to baseline's SignedLog1p(index=0..5), without indexed writes."""

    def forward(self, tracks):
        values = tracks[..., :6]
        return torch.cat((values.sign() * values.abs().log1p(), tracks[..., 6:]), dim=-1)


class FloatMaskModel(Phase2NoHitModelWrapper):
    """CMSSW's FloatArrays carries masks as 0/1 float32 tensors."""

    def forward(self, *inputs):
        masks = [value.bool() if i % 2 else value for i, value in enumerate(inputs)]
        logits = super().forward(*masks)
        return logits.masked_fill(~masks[1], 0)


def load_model():
    config = OmegaConf.load(RUN / "config.yaml")
    model = instantiate(config.model)
    checkpoint = torch.load(RUN / "checkpoints/best.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model"])
    preprocessing = [torch.nn.Sequential(*instantiate(config.data[name].preprocessing)) for name in OBJECTS]
    # PyTorch's legacy exporter cannot export SignedLog1p's indexed assignment.
    preprocessing[0][0] = TrackLog()
    return FloatMaskModel(model, *preprocessing).eval(), config


@torch.inference_mode()
def main():
    torch.set_num_threads(1)
    wrapper, config = load_model()

    # Dummy shapes are enough for export; preprocessing is part of the graph.
    inputs = tuple(value for name in OBJECTS for value in
                   (torch.zeros(1, 2, config.data[name].dim), torch.ones(1, 2)))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model_path = OUTPUT / "model.onnx"
    dynamic_axes = {name: {0: "batch", 1: obj} for obj in OBJECTS
                    for name in (obj, f"{obj}_data_mask")}
    dynamic_axes["logits"] = {0: "batch", 1: "tracker_track"}
    torch.onnx.export(
        wrapper, inputs, model_path,
        input_names=INPUT_NAMES, output_names=["logits"],
        dynamic_axes=dynamic_axes, opset_version=17, dynamo=False,
    )
    print(f"Wrote {model_path}")


if __name__ == "__main__":
    main()
