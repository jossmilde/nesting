# Nesting Demo

This repository contains a small demo that converts uploaded STEP files into 2D profiles and nests them on available sheets using `run_nesting.py`.

## Thickness Matching

Every part and sheet must specify a numerical `thickness`. The nesting script will abort if it encounters a part with a thickness for which no sheet is defined. Ensure the thickness values match exactly.

