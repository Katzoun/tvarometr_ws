"""Runs one model over the test subset and writes raw per-class scores.

Deliberately writes scores by output *index*, not by label name. Which name
belongs to which index is a claim about the checkpoint, and claims belong in
scoring where they can be checked - that is exactly the bug this benchmark
exists to catch.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
from PIL import Image


class ResEmoteNetAdapter:
    """The model tvarometr ships today, loaded exactly the way the node loads it."""

    name = "resemotenet"
    num_classes = 7

    def __init__(self, weights, device, vendor_dir):
        sys.path.insert(0, str(vendor_dir))
        from resemotenet.ResEmoteNet import ResEmoteNet

        self.device = device
        self.model = ResEmoteNet().to(device)
        checkpoint = torch.load(weights, map_location=device, weights_only=False)
        # Checkpoints in the wild are either a bare state dict or wrapped in one
        # of a few conventional keys.
        state = checkpoint
        if isinstance(checkpoint, dict):
            for key in ("model_state_dict", "state_dict", "model"):
                if key in checkpoint:
                    state = checkpoint[key]
                    break
        self.model.load_state_dict(state)
        self.model.eval()

        # Same transform as the reference implementation and as the node.
        self.transform = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.Grayscale(num_output_channels=3),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def predict(self, pil_image):
        tensor = self.transform(pil_image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probabilities = F.softmax(self.model(tensor), dim=1)
        return probabilities.cpu().numpy().flatten()


ADAPTERS = {"resemotenet": ResEmoteNetAdapter}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="resemotenet", choices=sorted(ADAPTERS))
    ap.add_argument("--data", default="data/affectnet_val")
    ap.add_argument("--weights", default="/opt/tvarometr/models/affectnet7_model.pth")
    ap.add_argument("--vendor-dir",
                    default="/workspace/src/tvarometr_inference/tvarometr_inference/vendor")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    device = args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu"
    if device != args.device:
        print(f"{args.device} not available, falling back to {device}")

    data = Path(args.data)
    rows = list(csv.DictReader(open(data / "subset.csv")))
    print(f"{len(rows)} images from {data}")

    adapter = ADAPTERS[args.model](args.weights, device, Path(args.vendor_dir))
    out_path = Path(args.out or f"results/{args.model}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fields = ["file", "true_label", "argmax"] + [f"score_{i}" for i in range(adapter.num_classes)]
    elapsed = []
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            image = Image.open(data / "images" / row["file"]).convert("RGB")
            start = time.perf_counter()
            scores = adapter.predict(image)
            elapsed.append(time.perf_counter() - start)
            record = {"file": row["file"], "true_label": row["label"],
                      "argmax": int(np.argmax(scores))}
            record.update({f"score_{j}": f"{s:.6f}" for j, s in enumerate(scores)})
            writer.writerow(record)
            if i % 100 == 0:
                print(f"  {i}/{len(rows)}", end="\r", flush=True)

    per_image = np.median(elapsed) * 1000
    print(f"\nwrote {out_path}  ({per_image:.1f} ms/image median on {device})")


if __name__ == "__main__":
    main()
