# Nesting

This project provides a small Express server that invokes Python scripts for STEP processing and nesting.

## Installation

1. Install the Node dependencies:

```bash
npm install
```

2. Install the Python requirements (Shapely and Pyclipper are needed by the nesting script):

```bash
pip install -r requirements.txt
```

## Running the server

After installing the dependencies you can start the server with:

```bash
node server.js
```

The server exposes endpoints for uploading STEP files and starting a nesting job.

## Running the tests

Tests are written with `pytest`. The `npm test` script is configured to run the Python test suite.

```bash
npm test
```

This executes the tests located in the `tests/` directory.
=======
# Nesting Demo

This repository contains a small demo that converts uploaded STEP files into 2D profiles and nests them on available sheets using `run_nesting.py`.

## Thickness Matching

Every part and sheet must specify a numerical `thickness`. The nesting script will abort if it encounters a part with a thickness for which no sheet is defined. Ensure the thickness values match exactly.

## Debug Logging

By default the Python nesting script only logs high‑level information. Set the
environment variable `NESTING_DEBUG=1` before running `run_nesting.py` to enable
detailed debug output. This can help diagnose placement issues and analyse the
candidate search process.

=======
## Timing Statistics

Set the environment variable `NESTING_TIMING=1` to record how long heavy helper
functions take. When enabled a file `nesting_timing.log` is written after a run
listing the total and average time spent inside each decorated function.

## Front-end Toggles

The web interface now exposes checkboxes for `Debug` and `Timing`. When
selected these options set the `NESTING_DEBUG` and `NESTING_TIMING`
environment variables for the nesting run.

## Progress Bar

The main nesting loop now shows a progress bar while placing parts. Ensure the
`tqdm` package is installed (`pip install -r requirements.txt`). The bar writes
to `stderr` so JSON output on `stdout` is unaffected.

## Nesting Algorithms

`run_nesting.py` supports multiple algorithms selected via `parameters["nestingStrategy"]`.

- `DEFAULT` – heuristic placement using inner‑fit polygons.
- `RECTPACK` – rectangle packing based on bounding boxes.
- `SVG_NEST` – experimental strategy that builds no‑fit polygons with Pyclipper and searches for feasible positions similar to the SVGNest project.


