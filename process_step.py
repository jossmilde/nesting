# Bestand: process_step.py (Versie die DeprecationWarning fixt)

import sys
import json
import os
import time
import traceback
import math

# === OpenCASCADE/pythonocc Imports ===
try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Wire, TopoDS_Edge
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Pln, gp_Ax2, gp_Vec
    from OCC.Core.Poly import Poly_Triangulation, Poly_Triangle, Poly_Array1OfTriangle
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core import BRepGProp # Importeer de module zelf
    from OCC.Core.GCPnts import GCPnts_QuasiUniformAbscissa

except ImportError as e:
    print(json.dumps({"success": False, "error": f"Import Error: {e}"}), file=sys.stderr); sys.exit(1)

# --- Functie get_mesh_data (ongewijzigd) ---
def get_mesh_data(shape: TopoDS_Shape, deflection: float = 0.1):
    if shape is None or shape.IsNull(): return None
    try:
        mesh_util = BRepMesh_IncrementalMesh(shape, deflection, False, 0.5); mesh_util.Perform()
        if not mesh_util.IsDone(): mesh_util = BRepMesh_IncrementalMesh(shape, deflection * 5, False, 0.5); mesh_util.Perform()
        if not mesh_util.IsDone(): print("ERROR: BRepMesh failed.", file=sys.stderr); return None
    except Exception as mesh_err: print(f"ERROR: BRepMesh Exception: {mesh_err}\n{traceback.format_exc()}", file=sys.stderr); return None
    vertices = [] ; triangles_indices = [] ; vert_map = {} ; any_face_processed = False
    explorer = TopExp_Explorer(shape, TopAbs_FACE); face_index = 0
    while explorer.More():
        face = explorer.Current() ; face_index += 1;
        if face is None or face.IsNull() or not isinstance(face, TopoDS_Face): explorer.Next(); continue
        location = TopLoc_Location(); poly_triangulation = BRep_Tool.Triangulation(face, location)
        if poly_triangulation is None: explorer.Next(); continue
        try:
            if not hasattr(poly_triangulation, 'MapNodeArray') or not hasattr(poly_triangulation, 'MapTriangleArray'): raise AttributeError("Missing Map*Array")
            nodes_array = poly_triangulation.MapNodeArray(); triangles_array = poly_triangulation.MapTriangleArray()
            if nodes_array is None or nodes_array.Length()==0: raise ValueError("nodes_array invalid")
            if triangles_array is None or triangles_array.Length()==0: raise ValueError("triangles_array invalid")
        except Exception as triang_err: print(f"WARN: Face {face_index-1}: Skip mesh data: {triang_err}.", file=sys.stderr); explorer.Next(); continue
        any_face_processed = True; trsf = location.Transformation(); face_vertices_coords = []
        node_lower = nodes_array.Lower(); node_upper = nodes_array.Upper();
        if node_lower > node_upper: explorer.Next(); continue
        for i in range(node_lower, node_upper + 1):
             try: pnt = nodes_array.Value(i); pnt.Transform(trsf); face_vertices_coords.append((pnt.X(), pnt.Y(), pnt.Z()))
             except Exception as node_err: print(f"WARN: Face {face_index-1} Node {i} error: {node_err}", file=sys.stderr); continue
        local_to_global_map = {}; global_vert_offset = len(vertices) // 3
        for local_idx_0based, coords in enumerate(face_vertices_coords):
            vert_tuple = (round(coords[0], 6), round(coords[1], 6), round(coords[2], 6));
            if vert_tuple not in vert_map: global_idx = global_vert_offset; vert_map[vert_tuple] = global_idx; vertices.extend(coords); local_to_global_map[local_idx_0based] = global_idx; global_vert_offset += 1
            else: local_to_global_map[local_idx_0based] = vert_map[vert_tuple]
        reverse_order = (face.Orientation() == TopAbs_REVERSED)
        triangle_lower = triangles_array.Lower(); triangle_upper = triangles_array.Upper();
        if triangle_lower > triangle_upper: explorer.Next(); continue
        for i in range(triangle_lower, triangle_upper + 1):
             try:
                 triangle = triangles_array.Value(i); n1_local_1based = triangle.Value(1); n2_local_1based = triangle.Value(2); n3_local_1based = triangle.Value(3)
                 n1_local_0based = n1_local_1based - node_lower; n2_local_0based = n2_local_1based - node_lower; n3_local_0based = n3_local_1based - node_lower
                 glob_idx1 = local_to_global_map[n1_local_0based]; glob_idx2 = local_to_global_map[n2_local_0based]; glob_idx3 = local_to_global_map[n3_local_0based]
                 if reverse_order: triangles_indices.extend([glob_idx1, glob_idx3, glob_idx2])
                 else: triangles_indices.extend([glob_idx1, glob_idx2, glob_idx3])
             except (KeyError, IndexError, Exception) as tri_err: print(f"WARN: Face {face_index-1}: Skip tri {i}: {tri_err}", file=sys.stderr); continue
        explorer.Next()
    if not any_face_processed or not vertices or not triangles_indices: print("ERROR: No valid mesh data extracted.", file=sys.stderr); return None
    return { "vertices": vertices, "indices": triangles_indices }

# --- Functie: Analyseer Vlakke Zijdes (met fix DeprecationWarning) ---
def analyze_planar_faces(shape: TopoDS_Shape):
    if shape is None or shape.IsNull(): return [], None, None, {}
    planar_faces_info = [] ; face_map = {} ; face_idx = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current(); face_id = f"face_{face_idx}"; face_idx += 1
        if face is None or face.IsNull() or not isinstance(face, TopoDS_Face): explorer.Next(); continue
        try:
            surf = BRepAdaptor_Surface(face, True);
            if surf.GetType() == GeomAbs_Plane:
                plane = surf.Plane(); normal = plane.Axis().Direction();
                if face.Orientation() == TopAbs_REVERSED: normal.Reverse()
                props = GProp_GProps();
                # --- GEBRUIK STATIC CALL ---
                BRepGProp.brepgprop.SurfaceProperties(face, props)
                # --- EINDE ---
                area = props.Mass();
                if area > 1e-6:
                    centroid_pnt = props.CentreOfMass()
                    planar_faces_info.append({"id": face_id, "area": round(area, 4), "normal": [round(normal.X(), 6), round(normal.Y(), 6), round(normal.Z(), 6)], "centroid": [round(centroid_pnt.X(), 6), round(centroid_pnt.Y(), 6), round(centroid_pnt.Z(), 6)]})
                    face_map[face_id] = face # Store face object
        except Exception as face_analyze_err: print(f"WARN: Face {face_idx-1}: Error analysis: {face_analyze_err}", file=sys.stderr)
        explorer.Next()
    planar_faces_info.sort(key=lambda x: x["area"], reverse=True)
    largest_face_id = planar_faces_info[0]["id"] if planar_faces_info else None
    second_largest_face_id = planar_faces_info[1]["id"] if len(planar_faces_info) > 1 else None
    return planar_faces_info, largest_face_id, second_largest_face_id, face_map

# --- Functie: Extraheer 2D profiel (ongewijzigd t.o.v. Antwoord 70) ---
def extract_2d_profile(target_face: TopoDS_Face, num_points_per_edge: int = 50):
    # (Volledige code zoals in Antwoord 70)
    if target_face is None or target_face.IsNull(): return None
    try:
        surf_adaptor = BRepAdaptor_Surface(target_face, True)
        if surf_adaptor.GetType() != GeomAbs_Plane: print(f"WARN: Target face not planar.", file=sys.stderr); return None
        plane = surf_adaptor.Plane(); plane_origin = plane.Location(); plane_x_axis_dir = plane.XAxis().Direction(); plane_y_axis_dir = plane.YAxis().Direction()
        plane_x_vec = gp_Vec(plane_x_axis_dir); plane_y_vec = gp_Vec(plane_y_axis_dir) # Convert dirs to vecs
        outer_loop_points = [] ; inner_loops_points = []
        wire_explorer = TopExp_Explorer(target_face, TopAbs_WIRE); is_first_wire = True
        while wire_explorer.More():
            wire = wire_explorer.Current()
            if not isinstance(wire, TopoDS_Wire) or wire.IsNull(): wire_explorer.Next(); continue
            current_loop_2d_points = [] ; edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)
            edge_segments_3d = [] # Collect 3d points per edge
            while edge_explorer.More():
                edge = edge_explorer.Current()
                if edge is None or edge.IsNull() or not isinstance(edge, TopoDS_Edge): edge_explorer.Next(); continue
                try:
                    curve3d_adaptor = BRepAdaptor_Curve(edge, target_face); first_param = curve3d_adaptor.FirstParameter(); last_param = curve3d_adaptor.LastParameter()
                    edge_points_3d = []
                    if abs(last_param - first_param) < 1e-7: pnt3d = curve3d_adaptor.Value(first_param); edge_points_3d = [pnt3d]
                    else:
                        num_points = max(10, min(num_points_per_edge, 100)); discretizer = GCPnts_QuasiUniformAbscissa(curve3d_adaptor, num_points)
                        if not discretizer.IsDone(): print(f"WARN: Skip edge: Discretization failed.", file=sys.stderr); edge_explorer.Next(); continue # Skip edge
                        for i in range(1, discretizer.NbPoints() + 1):
                             try: pnt3d = curve3d_adaptor.Value(discretizer.Parameter(i)); edge_points_3d.append(pnt3d)
                             except Exception as disc_val_err: print(f"WARN: Skip point {i}: {disc_val_err}", file=sys.stderr)
                    if edge_points_3d: # Add segment if points were generated
                        if edge.Orientation() == TopAbs_REVERSED: edge_segments_3d.append(list(reversed(edge_points_3d)))
                        else: edge_segments_3d.append(edge_points_3d)
                except Exception as edge_err: print(f"ERROR: Edge processing exception: {edge_err}\n{traceback.format_exc()}", file=sys.stderr) # Log but continue edge loop
                edge_explorer.Next()
            # --- Einde Edge Loop ---
            current_loop_raw_3d = []; last_pt_3d = None # Stitch segments
            if edge_segments_3d:
                 for segment in edge_segments_3d:
                     if not segment: continue
                     start_index = 0 # FIX from Antwoord 70
                     if last_pt_3d and segment[0] and last_pt_3d.IsEqual(segment[0], 1e-6): start_index = 1
                     current_loop_raw_3d.extend(segment[start_index:])
                     if segment: last_pt_3d = segment[-1]
            # Projecteer naar 2D
            if current_loop_raw_3d:
                current_loop_2d_points = [] ; last_pt_2d = None
                for pnt3d in current_loop_raw_3d:
                    try:
                        vec = gp_Vec(plane_origin, pnt3d); x_coord = vec.Dot(plane_x_vec); y_coord = vec.Dot(plane_y_vec) # Use vec.Dot(vec)
                        current_pt_2d = [round(x_coord, 4), round(y_coord, 4)]
                        if last_pt_2d is None or abs(current_pt_2d[0]-last_pt_2d[0]) > 1e-5 or abs(current_pt_2d[1]-last_pt_2d[1]) > 1e-5: current_loop_2d_points.append(current_pt_2d); last_pt_2d = current_pt_2d
                    except Exception as proj_err: print(f"WARN: Point projection error: {proj_err}", file=sys.stderr)
                if len(current_loop_2d_points) > 1: # Sluit lus
                     first_pt = current_loop_2d_points[0]; last_pt = current_loop_2d_points[-1]
                     if abs(first_pt[0]-last_pt[0]) > 1e-5 or abs(first_pt[1]-last_pt[1]) > 1e-5: current_loop_2d_points.append(first_pt)
            # Wijs toe
            if current_loop_2d_points:
                 if is_first_wire: outer_loop_points = current_loop_2d_points; is_first_wire = False
                 else: inner_loops_points.append(current_loop_2d_points)
            wire_explorer.Next()
        # Einde wire loop
        if not outer_loop_points: print("ERROR: No outer loop found.", file=sys.stderr); return None
        return {"outer": outer_loop_points, "holes": inner_loops_points}
    except Exception as profile_err: print(f"ERROR: Profile extraction func failed: {profile_err}\n{traceback.format_exc()}", file=sys.stderr); return None

# --- Hoofdverwerkingsfunctie (met fix DeprecationWarning) ---
def process_step_file(file_path):
    start_time = time.time()
    if not os.path.exists(file_path): return {"success": False, "error": f"File not found: {file_path}"}
    reader = STEPControl_Reader(); status = reader.ReadFile(file_path)
    if status != IFSelect_RetDone: return {"success": False, "error": f"Cannot read STEP (status: {status})."}
    reader.TransferRoots(); shape = reader.Shape()
    if shape is None or shape.IsNull(): return {"success": False, "error": "No valid shape found."}

    mesh_data = get_mesh_data(shape, deflection=0.1) # Mesh data
    planar_faces_info, default_face_id, second_largest_face_id, face_map = [], None, None, {}
    try: planar_faces_info, default_face_id, second_largest_face_id, face_map = analyze_planar_faces(shape)
    except Exception as face_err: print(f"ERROR: Face analysis exception: {face_err}\n{traceback.format_exc()}", file=sys.stderr)

    all_profiles = {} # Haal ALLE profielen op
    if planar_faces_info and face_map:
        # print(f"INFO: Extracting profiles for {len(planar_faces_info)} planar faces...", file=sys.stderr) # Kan weg
        for face_info in planar_faces_info:
            face_id = face_info["id"];
            if face_id in face_map:
                try:
                    profile_data = extract_2d_profile(face_map[face_id])
                    if profile_data: all_profiles[face_id] = profile_data
                except Exception as profile_err: print(f"ERROR: Profile call exc for {face_id}: {profile_err}\n{traceback.format_exc()}", file=sys.stderr)

    thickness = None # Dikte berekening
    if default_face_id and second_largest_face_id and planar_faces_info:
        try:
            face1_info = next((f for f in planar_faces_info if f["id"] == default_face_id), None)
            face2_info = next((f for f in planar_faces_info if f["id"] == second_largest_face_id), None)
            if face1_info and face2_info and math.isclose(face1_info["area"], face2_info["area"], rel_tol=0.01):
                normal1 = gp_Dir(*face1_info["normal"]); normal2 = gp_Dir(*face2_info["normal"])
                if normal1.IsOpposite(normal2, 1e-5): centroid1 = gp_Pnt(*face1_info["centroid"]); centroid2 = gp_Pnt(*face2_info["centroid"]); vec_c1_c2 = gp_Vec(centroid1, centroid2); dist = abs(vec_c1_c2.Dot(gp_Vec(normal2))); thickness = round(dist, 4); print(f"INFO: Detected thickness: {thickness}", file=sys.stderr) # Houd deze INFO log
        except Exception as thick_err: print(f"ERROR: Thickness calc exception: {thick_err}\n{traceback.format_exc()}", file=sys.stderr)

    success_flag = bool(mesh_data or (planar_faces_info and all_profiles)) # Succes als we *iets* hebben
    duration = time.time() - start_time
    result = { "success": success_flag, "message": f"STEP verwerkt in {duration:.2f} sec." + (" (Met fouten)" if not success_flag else ""), "mesh": mesh_data, "facesInfo": planar_faces_info if planar_faces_info else None, "defaultFaceId": default_face_id, "secondLargestFaceId": second_largest_face_id, "profiles2d": all_profiles if all_profiles else None, "thickness": thickness, "originalFile": os.path.basename(file_path) }
    return {k: v for k, v in result.items() if v is not None}

# --- if __name__ == "__main__": ---
if __name__ == "__main__":
    if len(sys.argv) < 2: print(json.dumps({"success": False, "error": "Geen bestandspad opgegeven."}), file=sys.stderr); sys.exit(1)
    step_file_path = sys.argv[1]
    try: result = process_step_file(step_file_path); print(json.dumps(result, indent=4)); sys.exit(0 if result.get("success", False) else 1)
    except Exception as e: print(json.dumps({"success": False, "error": f"Onverwachte fout: {type(e).__name__}", "details": str(e), "traceback": traceback.format_exc()}), file=sys.stderr); sys.exit(1)