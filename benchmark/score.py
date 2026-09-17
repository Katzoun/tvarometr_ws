"""Scores a predictions file against a claimed index-to-label mapping.

Besides the usual metrics it checks the mapping itself: if some other assignment
of names to output indices would score better, the claimed one is probably wrong.
That is what went unnoticed in the node for a long time - every class but sadness
was reported as something else, and nothing in the pipeline could tell.
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

CANONICAL = ["anger", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"]

KNOWN_ORDERS = {
    # What our affectnet7_model.pth actually uses. Measured: 43.6% on a balanced
    # AffectNet val sample, and the best fitting permutation of the seven names.
    # This is also the standard AffectNet-8 order with contempt dropped.
    "checkpoint": ["neutral", "happiness", "sadness", "surprise", "fear", "disgust", "anger"],
    # What the upstream ResEmoteNet inference scripts use. Our weights are NOT
    # theirs - under this order the same predictions score 11.1%, below chance.
    "resemotenet_upstream": ["happiness", "surprise", "sadness", "anger", "disgust", "fear", "neutral"],
    # Plain alphabetical, what an ImageFolder would produce. 8.6%.
    "alphabetical": CANONICAL,
}


def confusion(true_labels, pred_labels, classes):
    index = {c: i for i, c in enumerate(classes)}
    m = np.zeros((len(classes), len(classes)), dtype=int)
    for t, p in zip(true_labels, pred_labels):
        m[index[t], index[p]] += 1
    return m


def per_class(matrix, classes):
    out = []
    for i, c in enumerate(classes):
        tp = matrix[i, i]
        support = matrix[i].sum()
        predicted = matrix[:, i].sum()
        recall = tp / support if support else 0.0
        precision = tp / predicted if predicted else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out.append((c, precision, recall, f1, support))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("--order", default="checkpoint",
                    help="named order from KNOWN_ORDERS, or a comma separated list")
    args = ap.parse_args()

    order = KNOWN_ORDERS.get(args.order) or [s.strip() for s in args.order.split(",")]
    if sorted(order) != sorted(CANONICAL):
        raise SystemExit(f"order must be a permutation of {CANONICAL}, got {order}")

    rows = list(csv.DictReader(open(args.predictions)))
    true_labels = [r["true_label"] for r in rows]
    pred_labels = [order[int(r["argmax"])] for r in rows]

    print(f"{Path(args.predictions).name}   order '{args.order}': {order}")
    print(f"{len(rows)} images, {len(set(true_labels))} classes\n")

    m = confusion(true_labels, pred_labels, CANONICAL)
    stats = per_class(m, CANONICAL)

    accuracy = np.trace(m) / m.sum()
    macro_f1 = np.mean([s[3] for s in stats])
    balanced = np.mean([s[2] for s in stats])
    print(f"accuracy          {accuracy:6.1%}      (chance is {1/len(CANONICAL):.1%})")
    print(f"balanced accuracy {balanced:6.1%}")
    print(f"macro F1          {macro_f1:6.3f}\n")

    print(f"{'class':<11} {'prec':>6} {'recall':>7} {'F1':>6} {'n':>5}")
    for c, p, r, f1, n in stats:
        print(f"{c:<11} {p:6.2f} {r:7.2f} {f1:6.2f} {n:5d}")

    print("\nconfusion matrix (rows = truth, columns = predicted)")
    print(f"{'':<11}" + "".join(f"{c[:5]:>7}" for c in CANONICAL))
    for i, c in enumerate(CANONICAL):
        print(f"{c:<11}" + "".join(f"{v:7d}" for v in m[i]))

    # Is some other assignment of names to indices a better fit?
    truth_index = {c: i for i, c in enumerate(CANONICAL)}
    counts = np.zeros((len(CANONICAL), len(CANONICAL)), dtype=int)
    for r in rows:
        counts[truth_index[r["true_label"]], int(r["argmax"])] += 1
    row_ind, col_ind = linear_sum_assignment(-counts)
    best = [None] * len(CANONICAL)
    for t, output_index in zip(row_ind, col_ind):
        best[output_index] = CANONICAL[t]
    hits = counts[row_ind, col_ind].sum()

    print("\nmapping check")
    if best == order:
        print("  the claimed order is also the best fitting one")
    else:
        print(f"  a different order fits better: {best}")
        print(f"  it would score {hits / counts.sum():.1%} against this order's {accuracy:.1%}")
        print("  either the claimed order is wrong, or the model is too weak to tell")


if __name__ == "__main__":
    main()
