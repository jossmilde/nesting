# ... (rest of nest.py remains the same until main)

def main():
    params = json.loads(sys.argv[1])
    os.makedirs('output', exist_ok=True)
    output_path = 'output/nested_result.stp'
    
    try:
        for key in ['sheetWidth', 'sheetHeight', 'numSheets', 'partDistance', 'borderDistance']:
            if params[key] < 0:
                raise ValueError(f"{key} cannot be negative")
        if not params['files']:
            raise ValueError("No STP files provided")
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return
    
    shapes, error = load_stp_files(params['files'], params['partCounts'], params['faceIndices'])
    if error:
        print(json.dumps({"error": error}))
        return
    
    print(f"Part counts: {params['partCounts']}")  # Debug
    nested, error = custom_nest(shapes, params['sheetWidth'], params['sheetHeight'],
                                params['numSheets'], params['partDistance'], params['borderDistance'])
    if error:
        print(json.dumps({"error": error}))
        return
    
    create_3d_output(shapes, nested, output_path)
    preview = [{"polygon": list(shapes[idx][1].exterior.coords), "x": x, "y": y} for idx, x, y, _ in nested]
    print(json.dumps({"preview": preview}))

if __name__ == "__main__":
    main()