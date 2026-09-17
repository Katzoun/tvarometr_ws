# Benchmark

Compares emotion models on identical inputs, outside ROS.

    python3 fetch_subset.py                                     # rebuild the test set from subset.csv
    python3 run_model.py --out results/<name>.csv [--weights <path>] [--crop square --margin 0.2]
    python3 score.py results/<name>.csv [--order resemotenet_upstream]

Run it from `/workspace/benchmark` in the inference dev container, which has torch,
the vendored model code and the weights.

By default the model sees the whole dataset image. `--crop box` runs the node's face
detector first and feeds the face box the way the node does, `--crop square` squares
it, and `--margin` grows either by that fraction of the box on each side.

The HF checkpoints are `neilchouGTX/ResEmoteNet_Four_datasets_BatchSize<N>`:

    curl -L --create-dirs -o weights/ResEmoteNetBS64.pth \
      https://huggingface.co/neilchouGTX/ResEmoteNet_Four_datasets_BatchSize64/resolve/main/ResEmoteNetBS64.pth

`run_model.py` writes scores by output index and never names them. Naming happens
in `score.py`, which also checks the claimed order against the best fitting one -
a scrambled mapping is invisible in normal use and costs most of the accuracy.

## Results so far

700 images, 100 per class, from the Mauregato/affectnet_short val split, whole images.

| checkpoint | accuracy | macro F1 | class order |
|---|---|---|---|
| ours (models/affectnet7_model.pth) | 43.6% | 0.418 | AffectNet standard |
| ResEmoteNet BS32 (HF) | 59.9% | - | upstream ResEmoteNet |
| ResEmoteNet BS64 (HF) | 60.1% | 0.601 | upstream ResEmoteNet |
| ResEmoteNet BS128 (HF) | 58.3% | - | upstream ResEmoteNet |

Ours over-reports anger (26.9% of a balanced set) and rarely says neutral
(6.0%, recall 0.16), which matches the complaint that the emotion output feels
wrong at events, where most visitors are close to neutral.

The alternatives were trained by third parties on unknown data, so overlap with
this test set cannot be ruled out. None of this predicts venue performance -
that needs photos from the actual camera.
