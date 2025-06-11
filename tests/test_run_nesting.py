import json
import subprocess
import sys
import tempfile
from pathlib import Path



def test_run_nesting_simple():
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "square",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {
                    "outer": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
                }
            }
        ],
        "sheets": [
            {
                "id": "s1",
                "quantity": 1,
                "thickness": 1,
                "width": 100,
                "height": 100
            }
        ],
        "parameters": {
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "2",
            "bestFitScore": "YX"
        }
    }

    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"

    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)

        result = subprocess.run(
            [sys.executable, str(run_script), str(job_file)],
            capture_output=True,
            text=True,
            check=True,
        )

    data = json.loads(result.stdout)
    assert data["success"] is True
    assert len(data["placements"]) == 1
    assert data["unplaced"] == []


def test_run_nesting_shelf_algorithm():
    """Ensure the SHELF strategy executes and returns a placement."""
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "square",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {"outer": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]},
            }
        ],
        "sheets": [
            {"id": "s1", "quantity": 1, "thickness": 1, "width": 50, "height": 50}
        ],
        "parameters": {
            "nestingStrategy": "SHELF",
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "2",
            "bestFitScore": "YX",
        },
    }

    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"

    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)

        result = subprocess.run(
            [sys.executable, str(run_script), str(job_file)],
            capture_output=True,
            text=True,
            check=True,
        )

    data = json.loads(result.stdout)
    assert data["success"] is True
    assert len(data["placements"]) == 1
    assert data["unplaced"] == []

def test_shelf_rotation_applied():
    """Parts taller than wide should rotate 90 degrees in SHELF algorithm."""
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "rect",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {"outer": [[0,0],[10,0],[10,20],[0,20],[0,0]]},
            }
        ],
        "sheets": [
            {"id": "s1", "quantity": 1, "thickness": 1, "width": 50, "height": 50}
        ],
        "parameters": {
            "nestingStrategy": "SHELF",
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "2",
            "bestFitScore": "YX",
        },
    }
    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"
    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)
        result = subprocess.run([
            sys.executable,
            str(run_script),
            str(job_file),
        ], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert len(data["placements"]) == 1
    assert abs(data["placements"][0]["rotation"]) == 90


def test_shelf_candidate_angles_used():
    """Rotation angles determined from the polygon should be honoured."""
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "tri",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {"outer": [[0,0],[2,10],[4,0],[0,0]]},
            }
        ],
        "sheets": [
            {"id": "s1", "quantity": 1, "thickness": 1, "width": 12, "height": 50}
        ],
        "parameters": {
            "nestingStrategy": "SHELF",
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "3",
            "bestFitScore": "YX",
        },
    }

    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"

    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)
        result = subprocess.run(
            [sys.executable, str(run_script), str(job_file)],
            capture_output=True,
            text=True,
            check=True,
        )

    data = json.loads(result.stdout)
    assert data["success"] is True
    assert len(data["placements"]) == 1
    rot = data["placements"][0]["rotation"]
    assert rot not in {0, 90, -90, 180, -180}


def test_shelf_angles_with_offset_polygon():
    """Ensure candidate angles combine auto angles and edge angles."""
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "diamond",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {"outer": [[0,5],[5,10],[10,5],[5,0],[0,5]]},
            }
        ],
        "sheets": [
            {"id": "s1", "quantity": 1, "thickness": 1, "width": 12, "height": 12}
        ],
        "parameters": {
            "nestingStrategy": "SHELF",
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "3",
            "bestFitScore": "YX",
        },
    }

    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"

    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)
        result = subprocess.run(
            [sys.executable, str(run_script), str(job_file)],
            capture_output=True,
            text=True,
            check=True,
        )

    data = json.loads(result.stdout)
    assert data["success"] is True
    assert len(data["placements"]) == 1
    rot = data["placements"][0]["rotation"]
    assert abs(abs(rot) - 45) < 0.01 or abs(abs(rot) - 135) < 0.01

def test_shelf_candidate_angles_used():
    """Rotation angles determined from the polygon should be honoured."""
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "tri",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {"outer": [[0,0],[2,10],[4,0],[0,0]]},
            }
        ],
        "sheets": [
            {"id": "s1", "quantity": 1, "thickness": 1, "width": 12, "height": 50}
        ],
        "parameters": {
            "nestingStrategy": "SHELF",
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "3",
            "bestFitScore": "YX",
        },
    }

    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"

    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)
        result = subprocess.run(
            [sys.executable, str(run_script), str(job_file)],
            capture_output=True,
            text=True,
            check=True,
        )

    data = json.loads(result.stdout)
    assert data["success"] is True
    assert len(data["placements"]) == 1
    rot = data["placements"][0]["rotation"]
    # Rotation should match one of the candidate angles returned by the helper
    import importlib.util, pathlib
    rn_path = pathlib.Path(__file__).resolve().parents[1] / "run_nesting.py"
    spec = importlib.util.spec_from_file_location("run_nesting", rn_path)
    rn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rn)
    poly = rn.create_shapely_polygon([[0,0],[2,10],[4,0]], None, "test")
    cand = rn.get_potential_rotation_angles(poly)
    assert round(rot, 2) in {round(a,2) for a in cand}
    assert rot != 90


def test_sheet_efficiency_calculated():
    """The SVG_NEST strategy should record sheet areas used."""
    job = {
        "parts": [
            {
                "id": "p1",
                "originalName": "square",
                "quantity": 1,
                "thickness": 1,
                "profile2d": {"outer": [[0,0],[10,0],[10,10],[0,10],[0,0]]},
            }
        ],
        "sheets": [
            {"id": "s1", "quantity": 1, "thickness": 1, "width": 20, "height": 20}
        ],
        "parameters": {
            "partToPartDistance": 0,
            "partToSheetDistance": 0,
            "allowRotation": "3",
            "bestFitScore": "YX",
        },
    }

    run_script = Path(__file__).resolve().parents[1] / "run_nesting.py"

    with tempfile.TemporaryDirectory() as tmp:
        job_file = Path(tmp) / "job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f)
        result = subprocess.run(
            [sys.executable, str(run_script), str(job_file)],
            capture_output=True,
            text=True,
            check=True,
        )

    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["statistics"]["totalEfficiency"] > 0
    assert data["sheetStatistics"][0]["usedArea"] > 0


