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

import cv2
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


class HSEmotionAdapter:
    """HSEmotion's enet_b2_7, a whole pickled timm model, loaded the way the node loads it."""

    name = "hsemotion"
    num_classes = 7

    def __init__(self, weights, device, vendor_dir):
        self.device = device
        self.model = torch.load(weights, map_location=device, weights_only=False).eval()
        # hsemotion's own transform for the b2 models: RGB at 260 px.
        self.transform = transforms.Compose([
            transforms.Resize((260, 260)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    predict = ResEmoteNetAdapter.predict


ADAPTERS = {"resemotenet": ResEmoteNetAdapter, "hsemotion": HSEmotionAdapter}


def face_crop(detector, image, crop, margin):
    """The largest face box, squared for "square", grown by `margin` of it per side.

    Returns (box, cut): box is None without a face, cut says the image edge clipped it.
    """
    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    detections = detector.predict(bgr)
    # Same clamped integer boxes the node crops with.
    boxes = [[int(v) for v in detections.get_bbox_by_ind(i, height, width)]
             for i in detections.get_bboxes_inds("face")]
    if not boxes:
        return None, False

    x1, y1, x2, y2 = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    w, h = x2 - x1, y2 - y1
    if crop == "square":
        w = h = max(w, h)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    half_w, half_h = w * (1 + 2 * margin) / 2, h * (1 + 2 * margin) / 2
    box = [round(cx - half_w), round(cy - half_h), round(cx + half_w), round(cy + half_h)]
    cut = box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height
    return (max(box[0], 0), max(box[1], 0), min(box[2], width), min(box[3], height)), cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="resemotenet", choices=sorted(ADAPTERS))
    ap.add_argument("--data", default="data/affectnet_val")
    ap.add_argument("--weights", default="/opt/tvarometr/models/affectnet7_model.pth")
    ap.add_argument("--vendor-dir",
                    default="/workspace/src/tvarometr_inference/tvarometr_inference/vendor")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--out", default=None)
    ap.add_argument("--crop", default="full", choices=["full", "box", "square"],
                    help="whole image, or the detected face box as the node crops it, or squared")
    ap.add_argument("--margin", type=float, default=0.0,
                    help="grow the face box by this fraction of its size on each side")
    ap.add_argument("--detector", default="/opt/tvarometr/models/yolov8x_person_face.pt")
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

    detector = None
    if args.crop != "full":
        sys.path.insert(0, str(args.vendor_dir))
        from mivolo.model.yolo_detector import Detector
        detector = Detector(args.detector, device)

    fields = ["file", "true_label", "argmax", "crop"] + [f"score_{i}" for i in range(adapter.num_classes)]
    elapsed = []
    found = cut_by_edge = 0
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            image = Image.open(data / "images" / row["file"]).convert("RGB")
            box = None
            if detector is not None:
                # Without a face the model gets the whole image.
                box, cut = face_crop(detector, image, args.crop, args.margin)
                if box is not None:
                    image = image.crop(box)
                    found += 1
                    cut_by_edge += cut
            start = time.perf_counter()
            scores = adapter.predict(image)
            elapsed.append(time.perf_counter() - start)
            record = {"file": row["file"], "true_label": row["label"],
                      "argmax": int(np.argmax(scores)),
                      "crop": " ".join(map(str, box)) if box else ""}
            record.update({f"score_{j}": f"{s:.6f}" for j, s in enumerate(scores)})
            writer.writerow(record)
            if i % 100 == 0:
                print(f"  {i}/{len(rows)}", end="\r", flush=True)

    per_image = np.median(elapsed) * 1000
    print(f"\nwrote {out_path}  ({per_image:.1f} ms/image median on {device})")
    if detector is not None:
        print(f"face found in {found}/{len(rows)}, {cut_by_edge} of those cut by the image edge")


if __name__ == "__main__":
    main()
