# Benchmark

Compares emotion models on identical inputs, outside ROS.

    python3 fetch_subset.py                 # rebuild the test set from subset.csv
    python3 run_model.py --weights <path>   # model -> per-class scores
    python3 score.py results/<name>.csv     # metrics + mapping check

Run it in the vision image, which already has torch and the vendored model code:

    docker run --rm --gpus all \
      -v "$PWD/benchmark:/benchmark" \
      -v "$PWD/models:/opt/tvarometr/models:ro" \
      -v "$PWD/src/tvarometr_inference:/workspace/src/tvarometr_inference:ro" \
      -w /benchmark tvarometr/vision:latest \
      python3 run_model.py

`run_model.py` writes scores by output index and never names them. Naming happens
in `score.py`, which also checks the claimed order against the best fitting one -
a scrambled mapping is invisible in normal use and costs most of the accuracy.

## Results so far

700 images, 100 per class, from the Mauregato/affectnet_short val split.

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
