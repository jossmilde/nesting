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
