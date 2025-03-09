import sys
import json
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.BRep import BRep_Builder
from OCC.Core.gp import gp_Trsf, gp_Vec  # Fixed typo: 'frompq' to 'from'
from OCC.Core.STEPControl import STEPControl_Reader

def generate_step(nest_json_path, output_step_path):
    with open(nest_json_path, 'r') as f:
        nest_data = json.load(f)

    compound_builder = BRep_Builder()
    compound = TopoDS_Compound()
    compound_builder.MakeCompound(compound)

    for part_idx, part in enumerate(nest_data['parts']):
        step_reader = STEPControl_Reader()
        status = step_reader.ReadFile(part['file'])
        if status != 1:
            print(f"Failed to read STEP file {part['file']}", file=sys.stderr)
            sys.exit(1)
        step_reader.TransferRoots()
        shape = step_reader.OneShape()

        part_positions = part.get('positions', nest_data['nesting']['positions'][:part['quantity']])
        for i, pos in enumerate(part_positions[:part['quantity']]):
            trsf = gp_Trsf()
            trsf.SetTranslation(gp_Vec(pos['x'], pos['y'], 0))  # XY plane, Z=0
            transform = BRepBuilderAPI_Transform(shape, trsf)
            transformed_shape = transform.Shape()
            print(f"Added {part['file']} at ({pos['x']}, {pos['y']}, 0)", file=sys.stderr)
            compound_builder.Add(compound, transformed_shape)

    step_writer = STEPControl_Writer()
    step_writer.Transfer(compound, STEPControl_AsIs)
    status = step_writer.Write(output_step_path)
    if status != 1:
        print(f"Failed to write STEP file to {output_step_path}", file=sys.stderr)
        sys.exit(1)
    print(f"Generated STEP file at {output_step_path}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: generate_step.py <nest_json_path> <output_step_path>", file=sys.stderr)
        sys.exit(1)
    generate_step(sys.argv[1], sys.argv[2])