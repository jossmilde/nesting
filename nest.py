import sys
import json
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps

def process_step_file(file_path):
    step_reader = STEPControl_Reader()
    status = step_reader.ReadFile(file_path)
    if status != 1:  # IFSelect_RetDone
        return {"error": "Failed to read STEP file"}

    step_reader.TransferRoots()
    shape = step_reader.OneShape()

    # Mesh the shape
    mesh = BRepMesh_IncrementalMesh(shape, 0.1)
    mesh.Perform()

    # Explore faces
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    faces = []
    vertices = []
    indices = []
    index_offset = 0

    while exp.More():
        face = topods.Face(exp.Current())
        props = GProp_GProps()
        brepgprop_SurfaceProperties(face, props)
        area = props.Mass()

        # Get triangulation
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, location)
        if triangulation:
            nodes = triangulation.Nodes()
            triangles = triangulation.Triangles()

            # Collect vertices
            face_vertices = []
            for i in range(1, nodes.Length() + 1):
                point = nodes.Value(i).Transformed(location.Transformation())
                vertex_index = len(vertices) // 3
                vertices.extend([point.X(), point.Y(), point.Z()])
                face_vertices.append(vertex_index)

            # Collect indices for this face
            for i in range(1, triangles.Length() + 1):
                t = triangles.Value(i)
                indices.extend([face_vertices[t.Value(1) - 1], face_vertices[t.Value(2) - 1], face_vertices[t.Value(3) - 1]])

            faces.append({
                "area": area,
                "index_start": index_offset,
                "index_count": triangles.Length() * 3
            })
            index_offset += triangles.Length() * 3

        exp.Next()

    print(f"Found {len(faces)} faces", file=sys.stderr)
    return {
        "faces": faces,
        "mesh": {
            "vertices": vertices,
            "indices": indices
        },
        "color": {"r": 0.5, "g": 0.5, "b": 0.5}
    }

def main():
    if len(sys.argv) != 5:
        print(json.dumps({"error": "Usage: nest.py <file_path> <sheet_width> <sheet_height> <spacing>"}))
        return

    file_path, sheet_width, sheet_height, spacing = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    result = process_step_file(file_path)

    if "error" not in result:
        # Simulate nesting (simplified for now)
        result["nesting"] = {
            "positions": [{"x": 0, "y": 0}],  # Placeholder: one part at origin
            "sheet_width": sheet_width,
            "sheet_height": sheet_height,
            "spacing": spacing
        }

    print(json.dumps(result))

if __name__ == "__main__":
    main()