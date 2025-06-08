#!/usr/bin/env python
# run_nesting.py (v0.19.1-diag-nolimit - met automatische simplificatie, automatische rotatiehoekbepaling en SVG-export)

import sys
import json
import os
import traceback
import time
from collections import defaultdict
import math
import logging
import numpy as np

# --- Instellingen (aanpassen indien gewenst) ---
_OUTPUT_SVG = True  # Als True, wordt voor elk geplaatst onderdeel de SVG-paddata meegeleverd in de JSON-output.
_ENABLE_DEEP_DEBUG = False  # Zet op True voor volledige debug-output
# Overschrijf via omgevingsvariabele voor debugging
if os.environ.get("NESTING_DEBUG") == "1":
    _ENABLE_DEEP_DEBUG = True

# --- Imports (incl. STRtree) en Constanten ---
try:
    from shapely.geometry import Polygon, Point, MultiPolygon, box as shapely_box, LinearRing
    from shapely.affinity import translate, rotate
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    HAS_SHAPELY = True
except ImportError:
    print("ERROR: Shapely library not found (or STRtree missing). Please install/update: pip install shapely", file=sys.stderr)
    HAS_SHAPELY = False

try:
    import pyclipper
    HAS_PYCLIPPER = True
    CLIPPER_SCALE = 10000.0
except ImportError:
    print("ERROR: Pyclipper library not found. Please install it: pip install pyclipper", file=sys.stderr)
    HAS_PYCLIPPER = False

TOLERANCE = 1e-5
ZERO_TOLERANCE = 1e-9
INDEX_THRESHOLD = 10         # drempel voor STRtree-updates
_OVERLAP_DIST_THRESHOLD = 1e-3  # extra drempel voor overlapcontrole

# --- Hulpfuncties ---

def format_error(message, details=None):
    error_obj = {"success": False, "message": message}
    try:
        if details:
            error_obj["error_details"] = str(details)
            logging.error(f"FATAL_ERROR_DETAILS: {details}")
        logging.error(f"FATAL ERROR: {message}")
        logging.shutdown()
    except Exception:
        print(f"FATAL ERROR (logging failed): {message}\nDetails: {details}", file=sys.stderr)
    print(json.dumps(error_obj))
    sys.exit(1)

def calculate_bounding_box(points):
    if not points or not isinstance(points, list) or len(points) < 1:
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0, "area": 0}
    try:
        valid_points = [(p[0], p[1]) for p in points 
                        if isinstance(p, (list, tuple)) and len(p)==2 
                        and all(isinstance(c, (int, float)) and not math.isinf(c) and not math.isnan(c) for c in p)]
        if not valid_points:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0, "area": 0}
        min_x = min(p[0] for p in valid_points)
        max_x = max(p[0] for p in valid_points)
        min_y = min(p[1] for p in valid_points)
        max_y = max(p[1] for p in valid_points)
        width = max(0.0, round(max_x-min_x, 4))
        height = max(0.0, round(max_y-min_y, 4))
        area = round(width*height, 4)
        return {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y, "width": width, "height": height, "area": area}
    except Exception as bbox_err:
        logging.error(f"ERROR calculating bbox: {bbox_err}...")
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0, "area": 0}

def create_shapely_polygon(outer_coords, hole_coords_list, part_id_for_log):
    if not outer_coords or len(outer_coords) < 3:
        logging.warning(f"Skipping {part_id_for_log}: Not enough outer coords.")
        return None
    try:
        outer_shapely = [(p[0], p[1]) for p in outer_coords 
                         if isinstance(p, (list, tuple)) and len(p)==2 and 
                         all(isinstance(c, (int, float)) and not math.isinf(c) and not math.isnan(c) for c in p)]
        if len(outer_shapely) < 3:
            logging.warning(f"Skipping {part_id_for_log}: Not enough valid outer coords.")
            return None
        if Point(outer_shapely[0]).distance(Point(outer_shapely[-1])) > TOLERANCE:
            outer_shapely.append(outer_shapely[0])
        if len(outer_shapely) < 4:
            logging.warning(f"Skipping {part_id_for_log}: Outer requires >= 3 unique points.")
            return None
        holes_shapely = []
        if hole_coords_list:
            for i, hole in enumerate(hole_coords_list):
                if hole and len(hole) >= 3:
                    hole_pts = [(p[0], p[1]) for p in hole
                                if isinstance(p, (list, tuple)) and len(p)==2 and
                                all(isinstance(c, (int, float)) and not math.isinf(c) and not math.isnan(c) for c in p)]
                    if len(hole_pts) >= 3:
                        if Point(hole_pts[0]).distance(Point(hole_pts[-1])) > TOLERANCE:
                            hole_pts.append(hole_pts[0])
                        if len(hole_pts) >= 4:
                            try:
                                lr = LinearRing(hole_pts)
                                if lr.is_valid and not lr.is_empty:
                                    outer_poly_check = Polygon(outer_shapely)
                                    if outer_poly_check.buffer(-TOLERANCE).contains(Point(lr.coords[0])):
                                        holes_shapely.append(hole_pts)
                                    else:
                                        logging.warning(f"Skipping hole {i} in {part_id_for_log}: Outside outer boundary.")
                                else:
                                    logging.warning(f"Skipping hole {i} in {part_id_for_log}: Invalid Ring.")
                            except Exception as ring_err:
                                logging.warning(f"Skipping hole {i} in {part_id_for_log} (Ring error): {ring_err}")
                        else:
                            logging.warning(f"Skipping hole {i} in {part_id_for_log}: Hole requires >= 3 unique points.")
                else:
                    logging.warning(f"Skipping hole {i} in {part_id_for_log}: Not enough coords.")
        shapely_poly = Polygon(outer_shapely, holes_shapely)
        if not shapely_poly.is_valid:
            logging.warning(f"Poly {part_id_for_log} invalid. Buffering(0). Reason: {getattr(shapely_poly, 'validation_reason', 'N/A')}")
            shapely_poly = shapely_poly.buffer(0)
            if not shapely_poly.is_valid:
                logging.error(f"ERROR: Poly {part_id_for_log} invalid after buffer(0). Skip.")
                return None
        if abs(shapely_poly.area) < ZERO_TOLERANCE:
            logging.warning(f"Skipping {part_id_for_log}: Zero area.")
            return None
        return shapely_poly
    except Exception as e:
        logging.error(f"ERROR creating Shapely poly {part_id_for_log}: {e}\n{traceback.format_exc()}")
        return None

def get_potential_rotation_angles(polygon):
    """ Bereken potentiële 'goede' rotatiehoeken (OBB en edge angles). """
    if not polygon or not polygon.is_valid or abs(polygon.area) < ZERO_TOLERANCE:
        return [0.0]
    potential_angles_deg = set()
    tol_sq = TOLERANCE * TOLERANCE
    try:
        mrr = polygon.minimum_rotated_rectangle
        if mrr and not mrr.is_empty and isinstance(mrr, Polygon):
            coords = list(mrr.exterior.coords)
            if len(coords) >= 5:
                vec1 = (coords[1][0]-coords[0][0], coords[1][1]-coords[0][1])
                vec2 = (coords[2][0]-coords[1][0], coords[2][1]-coords[1][1])
                side1_len_sq = vec1[0]**2+vec1[1]**2
                side2_len_sq = vec2[0]**2+vec2[1]**2
                dx, dy = vec1 if side1_len_sq >= side2_len_sq else vec2
                if abs(dx) > ZERO_TOLERANCE or abs(dy) > ZERO_TOLERANCE:
                    obb_angle_rad = math.atan2(dy, dx)
                    obb_angle_deg = math.degrees(obb_angle_rad)
                    angle1 = -obb_angle_deg
                    angle2 = angle1 + 90.0
                    potential_angles_deg.add(round((angle1+180)%360-180, 2))
                    potential_angles_deg.add(round((angle2+180)%360-180, 2))
    except Exception as e:
        logging.warning(f"Could not calculate OBB angles: {e}")
    try:
        exterior_coords = list(polygon.exterior.coords)
        if len(exterior_coords) >= 3:
            unique_segment_angles = set()
            for i in range(len(exterior_coords)-1):
                p1, p2 = exterior_coords[i], exterior_coords[i+1]
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                if (dx*dx+dy*dy) < tol_sq:
                    continue
                if abs(dx) > ZERO_TOLERANCE or abs(dy) > ZERO_TOLERANCE:
                    segment_angle_rad = math.atan2(dy, dx)
                    segment_angle_deg_norm = round(math.degrees(segment_angle_rad) % 180, 1)
                    if segment_angle_deg_norm not in unique_segment_angles:
                        unique_segment_angles.add(segment_angle_deg_norm)
                        segment_angle_deg = math.degrees(segment_angle_rad)
                        angle1 = -segment_angle_deg
                        angle2 = angle1 + 90.0
                        potential_angles_deg.add(round((angle1+180)%360-180, 2))
                        potential_angles_deg.add(round((angle2+180)%360-180, 2))
    except Exception as e:
        logging.warning(f"Could not calculate exterior segment angles: {e}")
    if not potential_angles_deg:
        potential_angles_deg.add(0.0)
    return sorted(list(potential_angles_deg))

def scale_point_to_clipper(point):
    return (int(round(point[0]*CLIPPER_SCALE)), int(round(point[1]*CLIPPER_SCALE)))

def scale_point_from_clipper(point):
    return (float(point[0])/CLIPPER_SCALE, float(point[1])/CLIPPER_SCALE)

def scale_paths_from_clipper(paths):
    return [[scale_point_from_clipper(p) for p in path] for path in paths]

def shapely_to_clipper(polygon):
    if not polygon or polygon.is_empty or not polygon.is_valid:
        return []
    paths = []
    try:
        geoms = []
        if isinstance(polygon, MultiPolygon):
            geoms.extend(list(polygon.geoms))
        elif isinstance(polygon, Polygon):
            geoms.append(polygon)
        else:
            logging.warning(f"Unsupported geometry type for Clipper conversion: {type(polygon)}")
            return []
        for poly in geoms:
            if not isinstance(poly, Polygon) or poly.is_empty or not poly.is_valid:
                continue
            exterior_coords = list(poly.exterior.coords)
            scaled_exterior = [scale_point_to_clipper(p) for p in exterior_coords[:-1]]
            if len(scaled_exterior) >= 3:
                if pyclipper.Area(scaled_exterior) < 0:
                    scaled_exterior.reverse()
                paths.append(scaled_exterior)
            else:
                logging.warning("Skipping exterior with < 3 points in shapely_to_clipper.")
                continue
            for interior in poly.interiors:
                interior_coords = list(interior.coords)
                scaled_interior = [scale_point_to_clipper(p) for p in interior_coords[:-1]]
                if len(scaled_interior) >= 3:
                    if pyclipper.Area(scaled_interior) > 0:
                        scaled_interior.reverse()
                    paths.append(scaled_interior)
                else:
                    logging.warning("Skipping interior with < 3 points in shapely_to_clipper.")
        return paths
    except Exception as e:
        logging.error(f"Error in shapely_to_clipper: {e}")
        return []

def clipper_to_shapely(solution_paths):
    if not solution_paths:
        return None
    scaled_paths = scale_paths_from_clipper(solution_paths)
    polygons = []
    for path in scaled_paths:
        if len(path) >= 3:
            try:
                poly = Polygon(path)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_valid and abs(poly.area) > ZERO_TOLERANCE:
                    polygons.append(poly)
                elif not poly.is_valid:
                    logging.warning("Failed to create valid polygon from clipper path after buffer(0).")
            except Exception as e:
                logging.warning(f"Failed to create polygon from clipper path: {e}")
    if not polygons:
        return None
    try:
        final_geom = unary_union(polygons)
        if not final_geom.is_valid:
            final_geom = final_geom.buffer(0)
        if not final_geom.is_valid:
            logging.error("clipper_to_shapely: Geometry invalid after unary_union and buffer(0).")
            valid_polys = [p for p in polygons if p.is_valid and abs(p.area) > ZERO_TOLERANCE]
            if valid_polys:
                return max(valid_polys, key=lambda p: p.area)
            return None
        if isinstance(final_geom, Polygon):
            if abs(final_geom.area) < ZERO_TOLERANCE:
                return None
        elif isinstance(final_geom, MultiPolygon):
            final_geom = MultiPolygon([p for p in final_geom.geoms if abs(p.area) > ZERO_TOLERANCE])
            if final_geom.is_empty:
                return None
        return final_geom
    except Exception as e:
        logging.error(f"ERROR during unary_union in clipper_to_shapely: {e}")
        valid_polys = [p for p in polygons if p.is_valid and abs(p.area) > ZERO_TOLERANCE]
        if not valid_polys:
            return None
        if len(valid_polys) == 1:
            return valid_polys[0]
        try:
            return MultiPolygon(valid_polys)
        except Exception as mp_err:
            logging.error(f"Fallback to MultiPolygon failed: {mp_err}")
            return max(valid_polys, key=lambda p: p.area)

# --- Helper: Extra reductie voor vertexen (bijvoorbeeld voor een bijna-driehoek) ---
def reduce_polygon_vertices(poly, collinear_threshold=0.1):
    """
    Controleer de vertices en verwijder een punt als de afstand tussen dat punt en de lijn gevormd door zijn buren kleiner is dan de drempel.
    """
    coords = list(poly.exterior.coords)
    if coords[0] == coords[-1]:
        unique_coords = coords[:-1]
    else:
        unique_coords = coords[:]
    if len(unique_coords) <= 3:
        return poly
    reduced = []
    n = len(unique_coords)
    for i in range(n):
        p_prev = unique_coords[i-1]
        p_curr = unique_coords[i]
        p_next = unique_coords[(i+1) % n]
        dx = p_next[0] - p_prev[0]
        dy = p_next[1] - p_prev[1]
        seg_length = math.hypot(dx, dy)
        if seg_length == 0:
            dist = 0
        else:
            # Afstand van p_curr tot de lijn p_prev-p_next
            dist = abs(dx * (p_prev[1] - p_curr[1]) - dy * (p_prev[0] - p_curr[0])) / seg_length
        if dist < collinear_threshold:
            continue  # sla dit punt over
        else:
            reduced.append(p_curr)
    if len(reduced) < 3:
        reduced = unique_coords  # fallback
    reduced.append(reduced[0])
    return Polygon(reduced)

# --- Automatische simplificatie ---
def auto_simplify(poly):
    """ Vereenvoudig een polygon op basis van 2% van de omtrek, met min tol 0.5 en max 5.0 mm. """
    perimeter = poly.length
    tol = min(max(perimeter * 0.02, 0.5), 5.0)
    simp_poly = poly.simplify(tol, preserve_topology=True)
    return simp_poly, tol, perimeter

# --- Helper: Converteer Shapely polygon naar SVG path data ---
def polygon_to_svg(poly):
    """ Converteer een Shapely polygon naar een SVG path string (alleen de exterieur, geen holes). """
    coords = list(poly.exterior.coords)
    if not coords:
        return ""
    # Bouw een SVG-path: begin met "M", gevolgd door "L" voor elke volgende coördinaat, en sluit af met "Z"
    path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords) + " Z"
    return path

# --- Helper: evalueer kandidaatpunten ---
def evaluate_candidate_points(points_to_test, sheet, sheet_index, rotated_poly, rotated_ref_x, rotated_ref_y, rotation_angle, candidate_valid_area, candidate_buffer_amount):
    best_candidate = None
    for cand_idx, (px, py) in enumerate(points_to_test):
        trans_x = px - rotated_ref_x
        trans_y = py - rotated_ref_y
        candidate_poly_shapely = translate(rotated_poly, trans_x, trans_y)
        if not candidate_poly_shapely.within(candidate_valid_area):
            logging.debug(
                f"       Kandidaat {cand_idx+1} afgewezen: Niet volledig binnen geldig gebied."
            )
            continue
        if candidate_buffer_amount > ZERO_TOLERANCE:
            buffered_candidate = candidate_poly_shapely.buffer(candidate_buffer_amount, cap_style=1, join_style=1)
        else:
            buffered_candidate = candidate_poly_shapely
        if not buffered_candidate.is_valid:
            logging.warning(f"       Kandidaat {cand_idx+1} afgewezen: Gebufferde kandidaat ongeldig.")
            continue
        placed_buffers = sheet["placed_shapely_polygons_buffered"]
        if len(placed_buffers) < INDEX_THRESHOLD:
            nearby_polygons_to_check = placed_buffers
        else:
            tree = sheet.get("buffered_polygon_tree")
            if tree is None or (hasattr(tree, 'geometries') and len(tree.geometries) != len(placed_buffers)):
                tree = STRtree(placed_buffers)
                sheet["buffered_polygon_tree"] = tree
            nearby_polygons_to_check = tree.query(buffered_candidate.envelope)
            try:
                nearby_polygons_to_check = list(nearby_polygons_to_check)
            except Exception:
                nearby_polygons_to_check = []
            if nearby_polygons_to_check and isinstance(nearby_polygons_to_check[0], (int, np.integer)):
                nearby_polygons_to_check = [placed_buffers[i] for i in nearby_polygons_to_check if i < len(placed_buffers)]
        is_valid_final = True
        for existing_buffered_poly in nearby_polygons_to_check:
            if not hasattr(existing_buffered_poly, "geom_type"):
                continue
            if buffered_candidate.intersects(existing_buffered_poly):
                try:
                    intersection = buffered_candidate.intersection(existing_buffered_poly)
                    if intersection.area > 1e-2:
                        is_valid_final = False
                        logging.debug(
                            f"       Kandidaat {cand_idx+1} afgewezen: Overlap gedetecteerd (intersection area: {intersection.area})."
                        )
                        break
                except Exception as e:
                    is_valid_final = False
                    logging.debug(
                        f"       Kandidaat {cand_idx+1} afgewezen: Fout tijdens intersectiecheck: {e}."
                    )
                    break
        if is_valid_final:
            candidate_bounds = candidate_poly_shapely.bounds
            bbox_final = {
                "min_x": candidate_bounds[0],
                "min_y": candidate_bounds[1],
                "max_x": candidate_bounds[2],
                "max_y": candidate_bounds[3],
                "width": max(0.0, round(candidate_bounds[2]-candidate_bounds[0], 4)),
                "height": max(0.0, round(candidate_bounds[3]-candidate_bounds[1], 4))
            }
            current = {
                "sheet_instance": sheet,
                "sheet_index": sheet_index,
                "x": round(bbox_final['min_x'], 4),
                "y": round(bbox_final['min_y'], 4),
                "angle": rotation_angle,
                "width_bbox": bbox_final["width"],
                "height_bbox": bbox_final["height"],
                "placed_shapely_polygon": candidate_poly_shapely
            }
            if best_candidate is None:
                best_candidate = current
            else:
                best = best_candidate
                if current["x"] < best["x"] - TOLERANCE or (
                    abs(current["x"] - best["x"]) < TOLERANCE and current["y"] < best["y"] - TOLERANCE
                ):
                    best_candidate = current
    return best_candidate

# --- Rotatie-hoeken automatisch bepalen op basis van aantal segmenten ---
def determine_candidate_angles(num_segments):
    """ Als het aantal unieke segmenten (n) ≤ 10, dan:
        - Voor even n (centrale symmetrie): gebruik n/2 unieke hoeken, gelijkmatig verdeeld over 180°.
        - Voor oneven n: gebruik n unieke hoeken, gelijkmatig verdeeld over 360°.
        Alle hoeken worden teruggegeven in het interval [-180, 180).
    """
    if num_segments % 2 == 0:
        return sorted({ round(i * 180.0 / (num_segments/2), 2) for i in range(int(num_segments/2)) })
    else:
        return sorted({ round(i * 360.0 / num_segments, 2) for i in range(num_segments) })

# --- Hoofdfunctie ---
def main(job_file_path):
    # Logging setup
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nesting_run.log')
    log_level_file = logging.DEBUG if _ENABLE_DEEP_DEBUG else logging.INFO
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(level=log_level_file,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename=log_file_path,
                        filemode='w')
    logging.info("run_nesting.py v0.19.1-diag-nolimit (TEST: Geen IFP Limiet) gestart.")
    logging.info(f"Logbestand: {log_file_path}")
    if not HAS_SHAPELY:
        format_error("Shapely library (incl. STRtree) niet gevonden.")
    if not HAS_PYCLIPPER:
        format_error("Pyclipper library niet gevonden.")
    logging.info(f"Shapely & Pyclipper gevonden. Clipper Schaal: {CLIPPER_SCALE}")

    # Data laden
    start_time_loading = time.time()
    try:
        with open(job_file_path, 'r', encoding='utf-8') as f:
            job_data = json.load(f)
        logging.info(f"Job file '{job_file_path}' geladen ({time.time()-start_time_loading:.2f}s).")
    except Exception as e:
        format_error(f"Fout laden job file: {e}", traceback.format_exc())
    if not job_data:
        format_error("Job data leeg.")

    # Parameters en input data
    parts_in = job_data.get("parts", [])
    sheets_in = job_data.get("sheets", [])
    parameters = job_data.get("parameters", {})
    if not isinstance(parts_in, list):
        format_error("Input 'parts' geen lijst.")
    if not isinstance(sheets_in, list):
        format_error("Input 'sheets' geen lijst.")
    if not isinstance(parameters, dict):
        format_error("Input 'parameters' geen dict.")
    if not parts_in:
        format_error("Input 'parts' leeg.")
    if not sheets_in:
        format_error("Input 'sheets' leeg.")
    part_spacing = max(0.0, parameters.get("partToPartDistance", 0.0))
    sheet_margin = max(0.0, parameters.get("partToSheetDistance", 0.0))
    allowed_rotation_type = str(parameters.get("allowRotation", "2"))
    best_fit_score_strategy = parameters.get("bestFitScore", "YX").upper()
    logging.info(f"Parameters: partSpacing={part_spacing}, sheetMargin={sheet_margin}, allowRotation='{allowed_rotation_type}', bestFitScore='{best_fit_score_strategy}', maxIfpPoints=NO_LIMIT_TEST")

    # Data voorbereiden
    logging.info("Data voorbereiden...")
    start_time_prep = time.time()
    parts_to_place = []
    part_details = {}
    initial_unplaced_count = 0
    original_quantities = defaultdict(int)
    for part_idx, part in enumerate(parts_in):
        if not isinstance(part, dict):
            logging.warning(f"Skipping item 'parts' index {part_idx}: Not dict.")
            continue
        qty = part.get("quantity", 1)
        part_id = part.get("id")
        profile = part.get("profile2d")
        original_name = part.get("originalName", f"part_{part_idx}")
        thickness = part.get("thickness")
        if not part_id:
            part_id = f"autoID_{original_name}_{part_idx}"
        if not isinstance(qty, int) or qty < 0:
            logging.warning(f"Skipping {original_name} id:{part_id}: Invalid qty ({qty}). Set 0.")
            qty = 0
        original_quantities[original_name] += qty
        if qty == 0:
            continue
        if thickness is None:
            logging.warning(f"Skipping {qty}x {original_name} id:{part_id}: Missing thickness.")
            initial_unplaced_count += qty
            continue
        if not profile or not isinstance(profile, dict) or not profile.get("outer"):
            logging.warning(f"Skipping {qty}x {original_name} id:{part_id}: Missing/invalid profile.")
            initial_unplaced_count += qty
            continue
        shapely_poly = create_shapely_polygon(profile.get("outer"), profile.get("holes", []), f"{original_name} (id:{part_id})")
        if not shapely_poly:
            logging.warning(f"Skipping {qty}x {original_name} id:{part_id}: Invalid polygon.")
            initial_unplaced_count += qty
            continue
        # Vereenvoudig de polygon automatisch
        simp_poly, tol_used, perimeter = auto_simplify(shapely_poly)
        logging.debug(f"Simplify '{original_name}': Perimeter = {perimeter:.2f}, tolerance = {tol_used:.2f}. Segmenten: {len(list(simp_poly.exterior.coords))-1}")
        # Extra reductie voor bijna-driehoeken: als unique punten tussen 4 en 5 liggen, probeer redundante punten te verwijderen
        coords = list(simp_poly.exterior.coords)
        if coords[0] == coords[-1]:
            unique_count = len(coords) - 1
        else:
            unique_count = len(coords)
        if 3 < unique_count <= 5:
            simp_poly = reduce_polygon_vertices(simp_poly, collinear_threshold=0.1)
        shapely_poly = simp_poly

        bbox_0 = calculate_bounding_box(list(shapely_poly.exterior.coords))
        if bbox_0["width"] < ZERO_TOLERANCE or bbox_0["height"] < ZERO_TOLERANCE:
            logging.warning(f"Skipping {qty}x {original_name} id:{part_id}: Zero dimensions.")
            initial_unplaced_count += qty
            continue
        num_segments = len(list(shapely_poly.exterior.coords)) - 1
        logging.debug(f"Onderdeel '{original_name}' (id: {part_id}) final heeft {num_segments} lijnsegmenten.")
        # Gebruik de linkeronderhoek als referentiepunt (aangenomen dat STEP data zo gedefinieerd is)
        reference_point_0 = (bbox_0['min_x'], bbox_0['min_y'])
        base_potential_angles = get_potential_rotation_angles(shapely_poly)
        if num_segments <= 10:
            candidate_angles = determine_candidate_angles(num_segments)
            logging.debug(f"Automatisch bepaalde rotatiehoeken voor '{original_name}' (n={num_segments}): {candidate_angles}")
            possible_angles = candidate_angles
        else:
            possible_angles = base_potential_angles
        logging.debug(f"  Toegestane rotaties: {possible_angles}")
        part_details[part_id] = {
            "originalName": original_name,
            "thickness": thickness,
            "profile": profile,
            "bbox_0": bbox_0,
            "area": shapely_poly.area,
            "shapely_polygon_0": shapely_poly,
            "reference_point_0": reference_point_0,
            "potential_angles": possible_angles,
            "num_segments": num_segments
        }
        for i in range(qty):
            parts_to_place.append({
                "instance_id": f"{part_id}_inst_{i+1}",
                "original_id": part_id,
                "thickness": thickness
            })

    logging.debug("Unieke onderdelen met aantal lijnsegmenten:")
    for pid, details in part_details.items():
        logging.debug(f"Part '{details['originalName']}' (id: {pid}) heeft {details.get('num_segments', 'N/A')} lijnsegmenten. Mogelijke rotaties: {details.get('potential_angles')}")
    
    # Platen verwerken
    available_sheets = defaultdict(list)
    sheet_counter = 0
    sheet_id_map = {}
    for sheet_idx, sheet_def in enumerate(sheets_in):
        if not isinstance(sheet_def, dict):
            logging.warning(f"Skipping item in 'sheets' list (index {sheet_idx}): Not a dictionary.")
            continue
        qty = sheet_def.get("quantity", 1)
        thickness = sheet_def.get("thickness")
        width = sheet_def.get("width")
        height = sheet_def.get("height")
        orig_id = sheet_def.get('id', f'sheet_{sheet_idx}')
        if not isinstance(qty, int) or qty < 0:
            logging.warning(f"Skipping sheet {orig_id}: Invalid quantity ({qty}). Setting to 0.")
            qty = 0
        if qty == 0:
            continue
        if thickness is None or width is None or height is None:
            logging.warning(f"Skipping {qty}x sheet {orig_id}: Missing thickness/width/height.")
            continue
        if width <= ZERO_TOLERANCE or height <= ZERO_TOLERANCE:
            logging.warning(f"Skipping {qty}x sheet {orig_id}: Invalid dimensions ({width}x{height}).")
            continue
        try:
            sheet_polygon = shapely_box(0.0, 0.0, width, height)
            sheet_polygon_with_margin = sheet_polygon.buffer(-sheet_margin, cap_style=3, join_style=2) if sheet_margin > TOLERANCE else sheet_polygon
            if sheet_polygon_with_margin.is_empty or not sheet_polygon_with_margin.is_valid:
                logging.warning(f"Sheet {orig_id} unusable: Margin te groot. Skipping {qty} instances.")
                continue
            if isinstance(sheet_polygon_with_margin, MultiPolygon):
                sheet_polygon_with_margin = max(sheet_polygon_with_margin.geoms, key=lambda p: p.area)
            if not sheet_polygon_with_margin.is_valid or sheet_polygon_with_margin.is_empty:
                logging.warning(f"Sheet {orig_id} unusable na margin. Skipping {qty} instances.")
                continue
            sheet_clipper_paths = shapely_to_clipper(sheet_polygon_with_margin)
            if not sheet_clipper_paths:
                logging.warning(f"Could not convert sheet {orig_id} margin to Clipper. Skipping {qty} instances.")
                continue
            for i in range(qty):
                sheet_counter += 1
                sheet_inst_id = f"{orig_id}_inst_{sheet_counter}"
                sheet_instance = {
                    "id": sheet_inst_id,
                    "original_id": orig_id,
                    "width": width,
                    "height": height,
                    "thickness": thickness,
                    "sheet_polygon": sheet_polygon,
                    "sheet_polygon_with_margin": sheet_polygon_with_margin,
                    "sheet_clipper_paths": sheet_clipper_paths,
                    "placed_items": [],
                    "placed_original_polygons": [],
                    "placed_shapely_polygons_buffered": [],
                    "buffered_polygon_tree": None,
                    "candidate_points": [(sheet_margin, sheet_margin)]
                }
                available_sheets[thickness].append(sheet_instance)
                sheet_id_map[sheet_inst_id] = sheet_def
        except Exception as e:
            logging.error(f"Failed to prepare sheet {orig_id}: {e}\n{traceback.format_exc()}")
            continue

    logging.info(f"Voorbereiding voltooid ({time.time()-start_time_prep:.2f}s).")
    logging.info(f"{len(parts_to_place)} onderdeel-instanties te plaatsen.")
    total_sheets = sum(len(s) for s in available_sheets.values())
    logging.info(f"{total_sheets} plaat-instanties beschikbaar ({len(available_sheets)} diktes).")
    if initial_unplaced_count > 0:
        logging.warning(f"{initial_unplaced_count} onderdelen initieel overgeslagen.")

    # --- Nesting Algoritme ---
    logging.info("Start nesting (TEST: Geen IFP Limiet + STRtree)...")
    start_time_nesting = time.time()
    final_placements = []
    unplaced_parts_from_nesting = []
    try:
        parts_to_place.sort(key=lambda p: part_details[p["original_id"]]["area"], reverse=True)
    except Exception as sort_err:
        logging.warning(f"Sorteren mislukt: {sort_err}")
    for part_idx, part_instance in enumerate(parts_to_place):
        part_id = part_instance["original_id"]
        part_thickness = part_instance["thickness"]
        instance_id_log = part_instance["instance_id"]
        part_info = part_details.get(part_id)
        if not part_info:
            logging.error(f"Consistentiefout: Details {instance_id_log}. Skip.")
            unplaced_parts_from_nesting.append(part_instance)
            continue
        original_name = part_info["originalName"]
        original_shapely_polygon = part_info.get("shapely_polygon_0")
        if not original_shapely_polygon:
            logging.error(f"Consistentiefout: Poly {instance_id_log}. Skip.")
            unplaced_parts_from_nesting.append(part_instance)
            continue
        logging.info(f"[{part_idx+1}/{len(parts_to_place)}] Verwerken: {instance_id_log} ({original_name}) Dikte: {part_thickness}")
        logging.debug(f"Onderdeel '{original_name}' (id: {part_id}) heeft {part_info.get('num_segments', 'N/A')} lijnsegmenten.")
        reference_point = part_info["reference_point_0"]
        base_potential_angles = part_info.get("potential_angles", [0.0])
        num_segments = part_info.get("num_segments", 999)
        if num_segments <= 10:
            candidate_angles = determine_candidate_angles(num_segments)
            logging.debug(f"Automatisch bepaalde rotatiehoeken voor '{original_name}' (n={num_segments}): {candidate_angles}")
            possible_angles = candidate_angles
        else:
            possible_angles = base_potential_angles
        logging.debug(f"  Toegestane rotaties: {possible_angles}")
        best_placement_overall_for_part = None
        target_sheets = available_sheets.get(part_thickness, [])
        if not target_sheets:
            error_msg = (
                f"Geen platen beschikbaar voor dikte {part_thickness}. "
                "Onderdelen en platen moeten dezelfde thickness hebben."
            )
            format_error(error_msg)
        rotated_cache = {}
        for angle in possible_angles:
            if angle not in rotated_cache:
                try:
                    rotated_poly = rotate(original_shapely_polygon, angle, origin=(0,0), use_radians=False)
                    rotated_ref = rotate(Point(reference_point), angle, origin=(0,0), use_radians=False)
                    rotated_cache[angle] = (rotated_poly, rotated_ref.x, rotated_ref.y)
                except Exception as rotate_err:
                    logging.error(f"  Rotatie {instance_id_log} R:{angle} mislukt: {rotate_err}.")
                    continue
            rotated_shapely_polygon, rotated_ref_offset_x, rotated_ref_offset_y = rotated_cache[angle]
            for sheet_index, sheet in enumerate(target_sheets):
                logging.debug(f"    Checken plaat {sheet['id']} ({sheet_index+1}/{len(target_sheets)})")
                try:
                    pc = pyclipper.Pyclipper()
                    sheet_clipper_paths = sheet["sheet_clipper_paths"]
                    pc.AddPaths(sheet_clipper_paths, pyclipper.PT_SUBJECT, True)
                    if sheet["placed_shapely_polygons_buffered"]:
                        try:
                            forbidden_geom_shapely = unary_union(sheet["placed_shapely_polygons_buffered"])
                        except Exception as union_err:
                            logging.error(f"  Error union buffers sheet {sheet['id']}: {union_err}. Adding individually.")
                            forbidden_geom_shapely = None
                        if forbidden_geom_shapely and forbidden_geom_shapely.is_valid and not forbidden_geom_shapely.is_empty:
                            all_forbidden_paths = shapely_to_clipper(forbidden_geom_shapely)
                            if all_forbidden_paths:
                                pc.AddPaths(all_forbidden_paths, pyclipper.PT_CLIP, True)
                        else:
                            all_forbidden_paths = []
                            logging.warning(f"  Union buffers mislukt/empty sheet {sheet['id']}. Adding individually.")
                            for buff_poly in sheet["placed_shapely_polygons_buffered"]:
                                all_forbidden_paths.extend(shapely_to_clipper(buff_poly))
                            if all_forbidden_paths:
                                pc.AddPaths(all_forbidden_paths, pyclipper.PT_CLIP, True)
                    free_space_paths = pc.Execute(pyclipper.CT_DIFFERENCE, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)
                    if not free_space_paths:
                        logging.debug(f"      Geen vrije ruimte op plaat {sheet['id']}.")
                        continue
                    try:
                        pco_ifp = pyclipper.PyclipperOffset()
                        pco_ifp.AddPaths(free_space_paths, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
                        inner_fit_margin = max((part_spacing/2.0)+TOLERANCE, 0.01) * CLIPPER_SCALE
                        ifp_paths = pco_ifp.Execute(-inner_fit_margin)
                    except pyclipper.ClipperException as clip_ex:
                        logging.warning(f"  Pyclipper offset (IFP) exception sheet {sheet['id']}: {clip_ex}.")
                        continue
                    except Exception as ifp_err:
                        logging.error(f"  Fout bij IFP berekening sheet {sheet['id']}: {ifp_err}.")
                        continue
                    if not ifp_paths:
                        logging.debug(f"      IFP leeg na krimp op plaat {sheet['id']}.")
                        continue
                    ifp_shapely = clipper_to_shapely(ifp_paths)
                    if not ifp_shapely or ifp_shapely.is_empty:
                        logging.debug(f"      Kon IFP paden niet naar Shapely converteren op {sheet['id']}.")
                        continue
                    existing_candidate_points = sheet.get("candidate_points", [])

                    candidate_valid_area = sheet["sheet_polygon_with_margin"]
                    candidate_buffer_amount = (part_spacing/2.0) + TOLERANCE
                    best_placement_for_this_angle_sheet = None
                    if existing_candidate_points:
                        unique_cache = sorted(list({(round(p[0],4), round(p[1],4)) for p in existing_candidate_points}), key=lambda p: (p[0], p[1]))
                        logging.debug(f"      Cached punten te testen: {len(unique_cache)}")
                        best_placement_for_this_angle_sheet = evaluate_candidate_points(unique_cache, sheet, sheet_index, rotated_shapely_polygon, rotated_ref_offset_x, rotated_ref_offset_y, angle, candidate_valid_area, candidate_buffer_amount)

                    if best_placement_for_this_angle_sheet is None:
                        potential_points_raw = []
                        geoms_to_process = []
                        if isinstance(ifp_shapely, Polygon):
                            geoms_to_process.append(ifp_shapely)
                        elif isinstance(ifp_shapely, MultiPolygon):
                            geoms_to_process.extend(list(ifp_shapely.geoms))
                        for geom in geoms_to_process:
                            if isinstance(geom, Polygon) and not geom.is_empty:
                                potential_points_raw.extend(list(geom.exterior.coords)[:-1])
                        if not potential_points_raw:
                            logging.debug(f"      Geen IFP punten op {sheet['id']}.")
                            continue

                        unique_potential_points = {(round(p[0],4), round(p[1],4)) for p in potential_points_raw}
                        sorted_candidate_points = sorted(list(unique_potential_points), key=lambda p: (p[0], p[1]))
                        logging.debug(f"      Aantal IFP punten te testen: {len(sorted_candidate_points)}")
                        best_placement_for_this_angle_sheet = evaluate_candidate_points(sorted_candidate_points, sheet, sheet_index, rotated_shapely_polygon, rotated_ref_offset_x, rotated_ref_offset_y, angle, candidate_valid_area, candidate_buffer_amount)


                    if best_placement_for_this_angle_sheet:
                        if best_placement_overall_for_part is None:
                            best_placement_overall_for_part = best_placement_for_this_angle_sheet
                        else:
                            curr = best_placement_for_this_angle_sheet
                            best = best_placement_overall_for_part
                            if best_fit_score_strategy == "ORIGINDIST":
                                if (curr["x"]**2+curr["y"]**2) < (best["x"]**2+best["y"]**2) - TOLERANCE:
                                    best_placement_overall_for_part = curr
                            elif best_fit_score_strategy == "SHEETYX":
                                if curr["sheet_index"] < best["sheet_index"]:
                                    best_placement_overall_for_part = curr
                                elif curr["sheet_index"] == best["sheet_index"]:
                                    if curr["y"] < best["y"] - TOLERANCE or (abs(curr["y"] - best["y"]) < TOLERANCE and curr["x"] < best["x"] - TOLERANCE):
                                        best_placement_overall_for_part = curr
                            else:
                                if curr["y"] < best["y"] - TOLERANCE or (abs(curr["y"]-best["y"])<TOLERANCE and curr["x"]<best["x"]-TOLERANCE):
                                    best_placement_overall_for_part = curr
                except Exception as place_error:
                    logging.error(f"  Fout checken plaat {sheet['id']} hoek {angle}: {place_error}\n{traceback.format_exc()}")
                    continue
        if best_placement_overall_for_part:
            chosen_placement = best_placement_overall_for_part
            sheet_to_place_on = chosen_placement["sheet_instance"]
            final_poly = chosen_placement["placed_shapely_polygon"]
            final_angle = chosen_placement["angle"]
            final_x = chosen_placement["x"]
            final_y = chosen_placement["y"]
            final_w = chosen_placement["width_bbox"]
            final_h = chosen_placement["height_bbox"]
            placement_info = {
                "partInstanceId": instance_id_log,
                "partId": part_id,
                "originalName": original_name,
                "sheetId": sheet_to_place_on["id"],
                "x_bl_bbox": final_x,
                "y_bl_bbox": final_y,
                "width_bbox": final_w,
                "height_bbox": final_h,
                "rotation": final_angle,
                "profile2d": part_info.get("profile"),
                "bbox": {"x": final_x, "y": final_y, "width": final_w, "height": final_h}
            }
            # Indien SVG-output gewenst, voeg de SVG paddata toe (alleen de exterieur)
            if _OUTPUT_SVG:
                placement_info["svg"] = polygon_to_svg(final_poly)
                logging.debug(f"Placement {instance_id_log} SVG: {placement_info['svg']}")
            final_placements.append(placement_info)
            sheet_to_place_on["placed_items"].append(placement_info)
            sheet_to_place_on["placed_original_polygons"].append(final_poly)
            if (part_spacing/2.0+TOLERANCE) > ZERO_TOLERANCE:
                buffered_for_check = final_poly.buffer((part_spacing/2.0+TOLERANCE), cap_style=1, join_style=1)
                if not buffered_for_check.is_valid or buffered_for_check.is_empty:
                    logging.warning(f"  Buffer ongeldig {instance_id_log}. Fallback.")
                    buffered_for_check = final_poly
            else:
                buffered_for_check = final_poly
            sheet_to_place_on["placed_shapely_polygons_buffered"].append(buffered_for_check)
            if len(sheet_to_place_on["placed_shapely_polygons_buffered"]) % INDEX_THRESHOLD == 0:
                try:
                    sheet_to_place_on["buffered_polygon_tree"] = STRtree(sheet_to_place_on["placed_shapely_polygons_buffered"])
                    logging.debug(f"  STRtree bijgewerkt sheet {sheet_to_place_on['id']}, {len(sheet_to_place_on['placed_shapely_polygons_buffered'])} items.")
                except Exception as tree_error:
                    logging.error(f"  Fout update STRtree {sheet_to_place_on['id']}: {tree_error}")
                    sheet_to_place_on["buffered_polygon_tree"] = None
            # Update candidate points for bottom-left placement
            cp_list = sheet_to_place_on.get("candidate_points", [])
            cp_list.append((final_x + final_w + part_spacing, final_y))
            cp_list.append((final_x, final_y + final_h + part_spacing))
            valid_area = sheet_to_place_on["sheet_polygon_with_margin"]
            new_list = []
            for cx, cy in cp_list:
                pt = Point(cx, cy)
                if not valid_area.contains(pt):
                    continue
                overlap = False
                for buff in sheet_to_place_on["placed_shapely_polygons_buffered"]:
                    if pt.within(buff):
                        overlap = True
                        break
                if not overlap:
                    new_list.append((round(cx,4), round(cy,4)))
            # remove duplicates and sort by x,y
            sheet_to_place_on["candidate_points"] = sorted(list({(x,y) for x,y in new_list}), key=lambda p: (p[0], p[1]))
            logging.info(f"  ==> Geplaatst (TEST NoLimit): {instance_id_log} op {sheet_to_place_on['id']} @ ({final_x:.1f}, {final_y:.1f}) R:{final_angle:.1f}")
        else:
            unplaced_parts_from_nesting.append(part_instance)
            logging.warning(f"  Kon {instance_id_log} ({original_name}) niet plaatsen (geen geldige positie).")
    logging.info(f"Nesting loop voltooid ({time.time()-start_time_nesting:.2f}s).")
    logging.info("Resultaten formatteren...")
    unplaced_summary = defaultdict(lambda: {"count": 0, "originalName": ""})
    for item in unplaced_parts_from_nesting:
        part_id_unplaced = item["original_id"]
        name = part_details.get(part_id_unplaced, {}).get("originalName", item.get("instance_id", part_id_unplaced))
        unplaced_summary[part_id_unplaced]["count"] += 1
        unplaced_summary[part_id_unplaced]["originalName"] = name
    total_placed = len(final_placements)
    total_requested = sum(original_quantities.values())
    total_unplaced_from_nesting = len(unplaced_parts_from_nesting)
    total_unplaced_overall = total_unplaced_from_nesting + initial_unplaced_count
    if total_placed + total_unplaced_overall != total_requested:
        logging.warning(f"Consistentiecheck: Placed({total_placed}) + Unplaced({total_unplaced_overall}) = {total_placed+total_unplaced_overall} != Requested({total_requested}).")
    unplaced_list_summary = [{"id": k, "originalName": v["originalName"], "quantity": v["count"]} for k, v in unplaced_summary.items()]
    nesting_duration = round(time.time()-start_time_nesting, 2)
    prep_duration = round(start_time_nesting - start_time_prep, 2)
    load_duration = round(start_time_prep - start_time_loading, 2)
    statistics = {
        "totalPartsRequested": total_requested,
        "totalPartsPlaced": total_placed,
        "totalPartsUnplaced": total_unplaced_overall,
        "initiallySkipped": initial_unplaced_count,
        "unplacedDuringNesting": total_unplaced_from_nesting,
        "nestingTimeSeconds": nesting_duration,
        "preparationTimeSeconds": prep_duration,
        "loadingTimeSeconds": load_duration
    }
    result_json = {
        "success": True,
        "message": f"Nesting (v0.19.1-diag-nolimit TEST) voltooid. Placed: {statistics['totalPartsPlaced']}/{statistics['totalPartsRequested']}.",
        "placements": final_placements,
        "unplaced": unplaced_list_summary,
        "statistics": statistics
    }
    logging.info("Resultaat naar stdout sturen.")
    logging.info(f"Statistieken: {json.dumps(statistics)}")
    logging.shutdown()
    print(json.dumps(result_json, separators=(',', ':')))

if __name__ == "__main__":
    start_time_script = time.time()
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"success": False, "message": "Fout: Geen job file pad opgegeven."}), file=sys.stderr)
            sys.exit(1)
        job_file = sys.argv[1]
        main(job_file)
    except Exception as e:
        try:
            logging.exception(f"ONVERWACHTE FATALE FOUT: {e}")
        except Exception:
            print(f"FATAL UNHANDLED EXCEPTION (logging failed): {e}\n{traceback.format_exc()}", file=sys.stderr)
        error_output = {"success": False, "message": f"Onverwachte Fatale Fout: {e}", "error_details": traceback.format_exc()}
        print(json.dumps(error_output))
        sys.exit(1)
    finally:
        end_time_script = time.time()
        total_duration = end_time_script - start_time_script
        print(f"INFO: run_nesting.py script voltooid in {total_duration:.2f} seconden.", file=sys.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
