import sys
import json
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Dir, gp_Ax1, gp_Pnt
import math

def process_step_file(file_path):
    step_reader = STEPControl_Reader()
    status = step_reader.ReadFile(file_path)
    if status != 1:
        return {"error": f"Failed to read STEP file {file_path}"}

    step_reader.TransferRoots()
    shape = step_reader.OneShape()

    mesh = BRepMesh_IncrementalMesh(shape, 0.1)
    mesh.Perform()

    exp = TopExp_Explorer(shape, TopAbs_FACE)
    faces = []
    vertices = []
    indices = []
    index_offset = 0

    while exp.More():
        face = topods.Face(exp.Current())
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = props.Mass()

        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, location)
        if triangulation:
            nb_nodes = triangulation.NbNodes()
            nb_triangles = triangulation.NbTriangles()

            face_vertices = []
            for i in range(1, nb_nodes + 1):
                point = triangulation.Node(i).Transformed(location.Transformation())
                vertex_index = len(vertices) // 3
                vertices.extend([point.X(), point.Y(), point.Z()])
                face_vertices.append(vertex_index)

            for i in range(1, nb_triangles + 1):
                t = triangulation.Triangle(i)
                indices.extend([face_vertices[t.Value(1) - 1], face_vertices[t.Value(2) - 1], face_vertices[t.Value(3) - 1]])

            faces.append({
                "area": area,
                "index_start": index_offset,
                "index_count": nb_triangles * 3
            })
            index_offset += nb_triangles * 3

        exp.Next()

    # Rotate mesh so largest face lies in XY plane (Z up)
    largest_face_idx = max(range(len(faces)), key=lambda i: faces[i]["area"])
    start_idx = faces[largest_face_idx]["index_start"]
    count = faces[largest_face_idx]["index_count"]
    face_indices = indices[start_idx:start_idx + count]
    v1 = gp_Pnt(vertices[face_indices[0] * 3], vertices[face_indices[0] * 3 + 1], vertices[face_indices[0] * 3 + 2])
    v2 = gp_Pnt(vertices[face_indices[1] * 3], vertices[face_indices[1] * 3 + 1], vertices[face_indices[1] * 3 + 2])
    v3 = gp_Pnt(vertices[face_indices[2] * 3], vertices[face_indices[2] * 3 + 1], vertices[face_indices[2] * 3 + 2])

    # Compute normal of the largest face
    u = gp_Vec(v2.X() - v1.X(), v2.Y() - v1.Y(), v2.Z() - v1.Z())
    v = gp_Vec(v3.X() - v1.X(), v3.Y() - v1.Y(), v3.Z() - v1.Z())
    normal = u.Crossed(v)
    normal.Normalize()

    # Target up vector (Z-axis), converted to gp_Vec
    up_dir = gp_Dir(0, 0, 1)
    up = gp_Vec(up_dir.X(), up_dir.Y(), up_dir.Z())

    # Compute rotation to align normal with Z-axis
    rotated_vertices = vertices
    if abs(normal.Dot(up)) < 0.99:  # If not already aligned
        # Compute the axis of rotation (cross product of normal and up)
        axis_vec = normal.Crossed(up)
        if axis_vec.Magnitude() > 1e-6:  # Ensure axis is valid
            axis_vec.Normalize()
            axis = gp_Dir(axis_vec.X(), axis_vec.Y(), axis_vec.Z())
            # Compute angle between normal and up
            dot_product = normal.Dot(up)
            dot_product = max(min(dot_product, 1.0), -1.0)  # Clamp to avoid numerical errors
            angle = math.acos(dot_product)
            trsf = gp_Trsf()
            trsf.SetRotation(gp_Ax1(v1, axis), angle)
            
            # Apply transformation to all vertices
            rotated_vertices = []
            for i in range(0, len(vertices), 3):
                pnt = gp_Pnt(vertices[i], vertices[i + 1], vertices[i + 2])
                pnt.Transform(trsf)
                rotated_vertices.extend([pnt.X(), pnt.Y(), pnt.Z()])
        else:
            print(f"Warning: Could not compute rotation axis for {file_path}", file=sys.stderr)

    # Verify orientation: if largest face is still not in XY, force a 90° rotation around X-axis
    # Check the range of Z values after rotation
    z_values = [rotated_vertices[i + 2] for i in range(0, len(rotated_vertices), 3)]
    z_range = max(z_values) - min(z_values)
    if z_range > 10:  # If Z range is large, the largest face is not in XY
        print(f"Forcing 90° rotation around X-axis for {file_path}", file=sys.stderr)
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), math.pi / 2)  # Rotate 90° around X
        forced_rotated_vertices = []
        for i in range(0, len(rotated_vertices), 3):
            pnt = gp_Pnt(rotated_vertices[i], rotated_vertices[i + 1], rotated_vertices[i + 2])
            pnt.Transform(trsf)
            forced_rotated_vertices.extend([pnt.X(), pnt.Y(), pnt.Z()])
        rotated_vertices = forced_rotated_vertices

    print(f"Found {len(faces)} faces in {file_path}", file=sys.stderr)
    result = {
        "faces": faces,
        "mesh": {
            "vertices": rotated_vertices,
            "indices": indices
        },
        "color": {"r": 0.5, "g": 0.5, "b": 0.5}
    }
    return result

def main():
    if len(sys.argv) < 7:
        print(json.dumps({"error": "Usage: nest.py <file1> <qty1> [<file2> <qty2> ...] <sheet_width> <sheet_height> <spacing> <sheet_gap> <face_down>"}))
        return

    args = sys.argv[1:]
    file_qty_pairs = []
    i = 0
    while i < len(args) - 5:
        file_qty_pairs.append((args[i], int(args[i + 1])))
        i += 2

    sheet_width = float(args[-5])
    sheet_height = float(args[-4])
    spacing = float(args[-3])
    sheet_gap = float(args[-2])
    face_down = args[-1]

    parts = []
    for file_path, qty in file_qty_pairs:
        print(f"Processing file: {file_path}, quantity: {qty}", file=sys.stderr)
        result = process_step_file(file_path)
        if "error" in result:
            print(json.dumps(result))
            return
        parts.append({"file": file_path, "data": result, "quantity": qty})

    nesting_results = []
    positions = []
    current_x = sheet_gap
    current_y = sheet_gap

    total_parts = sum(part["quantity"] for part in parts)
    parts_per_row = int((sheet_width - 2 * sheet_gap) // (100 + spacing))

    for part in parts:
        faces = part["data"]["faces"]
        if face_down == "largest":
            face_idx = max(range(len(faces)), key=lambda i: faces[i]["area"])
        else:
            face_idx = int(face_down) if face_down.isdigit() and 0 <= int(face_down) < len(faces) else 0
        
        part_positions = []
        for _ in range(part["quantity"]):
            if len(positions) >= total_parts:
                break
            if current_x + 100 > sheet_width - sheet_gap:
                current_x = sheet_gap
                current_y += 100 + spacing
                if current_y + 100 > sheet_height - sheet_gap:
                    break
            part_positions.append({"x": current_x, "y": current_y})
            positions.append({"x": current_x, "y": current_y})
            current_x += 100 + spacing

        nesting_results.append({
            "file": part["file"],
            "quantity": part["quantity"],
            "face_down": face_idx,
            "mesh": part["data"]["mesh"],
            "color": part["data"]["color"],
            "positions": part_positions
        })

    result = {
        "nesting": {
            "positions": positions,
            "sheet_width": sheet_width,
            "sheet_height": sheet_height,
            "spacing": spacing,
            "sheet_gap": sheet_gap
        },
        "parts": nesting_results,
        "original_files": [file_path for file_path, _ in file_qty_pairs]
    }
    print("Generated result structure:", file=sys.stderr)
    print(result, file=sys.stderr)
    print(json.dumps(result))

if __name__ == "__main__":
    main()