"""Builds the fixed test subset used by the benchmark.

Pulls a balanced sample from a HuggingFace dataset through the rows API instead
of downloading the full shards - affectnethq is ~8 GB and we need a few hundred
images. The manifest records the row indices, so the same subset can be rebuilt
byte for byte later; the images themselves stay out of git.
"""

import argparse
import csv
import io
import json
import random
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Dataset vocabularies differ; everything downstream works in these seven names.
# contempt has no counterpart in a 7-class model, so those rows are dropped.
CANONICAL = {
    "anger": "anger", "angry": "anger",
    "disgust": "disgust", "disgusted": "disgust",
    "fear": "fear", "fearful": "fear",
    "happy": "happiness", "happiness": "happiness",
    "neutral": "neutral",
    "sad": "sadness", "sadness": "sadness",
    "surprise": "surprise", "surprised": "surprise",
}

ROWS_API = "https://datasets-server.huggingface.co/rows"
BATCH = 100


def _get(url, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == tries - 1:
                raise
    return None


def fetch_rows(dataset, config, split, offset, length):
    url = (f"{ROWS_API}?dataset={urllib.parse.quote(dataset, safe='')}"
           f"&config={config}&split={split}&offset={offset}&length={length}")
    return json.loads(_get(url))


def main():
    ap = argparse.ArgumentParser()
    # A held-out val split rather than train: these models are trained on
    # AffectNet, so scoring them on its training images would flatter them.
    ap.add_argument("--dataset", default="Mauregato/affectnet_short")
    ap.add_argument("--config", default="default")
    ap.add_argument("--split", default="val")
    ap.add_argument("--per-class", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--out", default="data/affectnet_val")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    head = fetch_rows(args.dataset, args.config, args.split, 0, 1)
    total = head["num_rows_total"]
    label_names = None
    for feat in head.get("features", []):
        if feat["name"] == "label":
            label_names = feat["type"].get("names")
    if not label_names:
        sys.exit("could not read the label names from the dataset info")
    print(f"{args.dataset}: {total} rows, classes: {label_names}")

    usable = [i for i, n in enumerate(label_names) if n.lower() in CANONICAL]
    skipped = [n for n in label_names if n.lower() not in CANONICAL]
    if skipped:
        print(f"skipping classes with no 7-class counterpart: {skipped}")

    rng = random.Random(args.seed)
    wanted = args.per_class
    buckets = {i: [] for i in usable}
    seen = set()

    # Classes sit in contiguous blocks, so random offsets spread across all of
    # them. Keep drawing batches until every class is full.
    while any(len(v) < wanted for v in buckets.values()):
        offset = rng.randrange(0, max(1, total - BATCH))
        if offset in seen:
            continue
        seen.add(offset)
        batch = fetch_rows(args.dataset, args.config, args.split, offset, BATCH)
        for r in batch["rows"]:
            idx, row = r["row_idx"], r["row"]
            label = row["label"]
            if label not in buckets:
                continue
            if len(buckets[label]) < wanted and all(idx != e[0] for e in buckets[label]):
                buckets[label].append((idx, row["image"]["src"]))
        done = sum(min(len(v), wanted) for v in buckets.values())
        print(f"  collected {done}/{wanted * len(usable)}", end="\r", flush=True)
        if len(seen) > 400:
            print("\ngave up looking for more rows")
            break

    print()
    manifest = []
    for label, items in sorted(buckets.items()):
        for idx, src in items[:wanted]:
            source_label = label_names[label]
            canonical = CANONICAL[source_label.lower()]
            name = f"{canonical}_{idx}.jpg"
            path = out / "images" / name
            if not path.exists():
                path.write_bytes(_get(src))
            manifest.append({"row_idx": idx, "label": canonical,
                             "source_label": source_label, "file": name})
        print(f"  {label_names[label]}: {len(items[:wanted])}")

    manifest.sort(key=lambda m: (m["label"], m["row_idx"]))
    with open(out / "subset.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["row_idx", "label", "source_label", "file"])
        w.writeheader()
        w.writerows(manifest)
    print(f"wrote {len(manifest)} rows to {out / 'subset.csv'}")


if __name__ == "__main__":
    main()
