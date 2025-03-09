import sys
import json
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
import OCC.Core.TopoDS as TopoDS
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.GProp import GProp_GProps
import OCC.Core.BRepGProp as BRepGProp
from OCC.Core.TopLoc import TopLoc_Location

def main():
    try:
        file_path = sys.argv[1]
        print(f"Processing file: {file_path}", file=sys.stderr)

        reader = STEPControl_Reader()
        status = reader.ReadFile(file_path)
        if status != 1:
            raise Exception(f"Failed to read STP file: status {status}")
        reader.TransferRoots()
        shape = reader.OneShape()
        print("Shape loaded successfully", file=sys.stderr)

        mesher = BRepMesh_IncrementalMesh(shape, 0.1)
        mesher.Perform()

        vertices, indices = [], []
        v_map = {}
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        faces = []
        face_indices_start = 0
        while exp.More():
            face = TopoDS.topods_Face(exp.Current())
            props = GProp_GProps()
            BRepGProp.brepgprop_SurfaceProperties(face, props)
            face_data = {
                "area": props.Mass(),
                "index_start": face_indices_start,
                "index_count": 0
            }

            loc = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation(face, loc)
            if triangulation:
                face_data["index_count"] = triangulation.NbTriangles() * 3
                face_indices_start += face_data["index_count"]
                for i in range(1, triangulation.NbNodes() + 1):
                    pnt = triangulation.Node(i)
                    key = (pnt.X(), pnt.Y(), pnt.Z())
                    if key not in v_map:
                        v_map[key] = len(vertices) // 3
                        vertices.extend([pnt.X(), pnt.Y(), pnt.Z()])
                for i in range(1, triangulation.NbTriangles() + 1):
                    t = triangulation.Triangle(i)
                    n1, n2, n3 = t.Get()
                    indices.extend([v_map[(triangulation.Node(n1).X(), triangulation.Node(n1).Y(), triangulation.Node(n1).Z())],
                                   v_map[(triangulation.Node(n2).X(), triangulation.Node(n2).Y(), triangulation.Node(n2).Z())],
                                   v_map[(triangulation.Node(n3).X(), triangulation.Node(n3).Y(), triangulation.Node(n3).Z())]])
            faces.append(face_data)
            exp.Next()
        print(f"Found {len(faces)} faces", file=sys.stderr)

        mesh = {"vertices": vertices, "indices": indices}
        output = {
            "faces": faces,
            "mesh": mesh,
            "color": {"r": 0.5, "g": 0.5, "b": 0.5}
        }
        print(json.dumps(output))
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()