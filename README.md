# Nesting Demo

This repository contains a small demo that converts uploaded STEP files into 2D profiles and nests them on available sheets using `run_nesting.py`.

## Thickness Matching

Every part and sheet must specify a numerical `thickness`. The nesting script will abort if it encounters a part with a thickness for which no sheet is defined. Ensure the thickness values match exactly.

## Debug Logging

By default the Python nesting script only logs high‑level information. Set the
environment variable `NESTING_DEBUG=1` before running `run_nesting.py` to enable
detailed debug output. This can help diagnose placement issues and analyse the
candidate search process.

## Timing Statistics

Set the environment variable `NESTING_TIMING=1` to record how long heavy helper
functions take. When enabled a file `nesting_timing.log` is written after a run
listing the total and average time spent inside each decorated function.

