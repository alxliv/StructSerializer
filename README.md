# StructSerializer

A powerful C++ struct serialization toolkit that automatically generates JSON serialization/deserialization code from PDB debug symbols.

## Overview

StructSerializer extracts C++ struct layout information from PDB files using the Debug Interface Access (DIA) SDK and generates type-safe C serialization wrappers that work with the [cJSON](https://github.com/DaveGamble/cJSON) library. This eliminates the need to manually write tedious serialization code for complex nested structures.

## Features

- **Automatic Type Discovery** - Extracts struct layouts, nested dependencies, and enums from PDB files
- **Full Type Support** - Handles primitives, arrays, nested structs, enums, and pointers
- **Dependency Resolution** - Automatically includes all dependent types in topological order
- **Type-Safe Generation** - Generates strongly-typed C functions for each struct
- **Multi-Format JSON Input** - Supports both single-struct and multi-type JSON formats
- **Encoding-Aware** - Automatically detects and handles UTF-8, UTF-16, and UTF-32 encoded files

## Project Structure

```
StructSerializer/
|-- py_helpers/
| |-- extract_layout.py # Extract struct info from PDB files
| |-- generate_c_wrappers.py # Generate C serialization code
|-- mytest/
| |-- mytypes.h # Example C++ struct definitions
| |-- mytest.cpp # Example usage
|-- README.md
```

## Prerequisites

### Python Dependencies
- Python3.6+
- `pydia2` - DIA SDK Python bindings for PDB parsing

Install with:
```bash
pip install pydia2
```

### C/C++ Dependencies
- Visual Studio2015+ (for C++14 support and PDB generation)
- [cJSON library](https://github.com/DaveGamble/cJSON) for JSON operations

## Quick Start

###1. Define Your Structs

Create your C++ structures with nested types and enums:

```c
// mytypes.h
typedef enum {
 COLOR_RED,
 COLOR_GREEN,
 COLOR_BLUE
} Color;

typedef struct {
 float x;
 float y;
} Point;

typedef struct {
 double width;
 double height;
} Size;

typedef struct {
 Point center;
 Size bounding;
 Color color;
 float values[5];
} myTestStruct;
```

###2. Compile with Debug Symbols

Build your C++ code with debug information enabled to generate a PDB file:

```bash
# Visual Studio: Build in Debug mode or with /Zi flag
cl /Zi /EHsc mytest\mytest.cpp /Fo:mytest.obj /Fe:mytest.exe
```

###3. Extract Struct Layout

Use `extract_layout.py` to parse the PDB and extract struct information:

```bash
python py_helpers/extract_layout.py x64/Debug/mytest.pdb myTestStruct > mystruct.json
```

This generates a JSON file containing the complete type information (multi-type example shown below).

###4. Generate Serialization Code

Use `generate_c_wrappers.py` to create the serialization functions:

```bash
python py_helpers/generate_c_wrappers.py --root myTestStruct --in mystruct.json --out-base myTestStruct_serial
```

This generates two files:
- `myTestStruct_serial.h` - Function declarations
- `myTestStruct_serial.c` - Function implementations

###5. Use in Your Code

Include the generated files and use the serialization functions:

```c
#include "myTestStruct_serial.h"
#include <cjson/cJSON.h>
#include <stdio.h>

int main() {
 myTestStruct s = {0};
 s.center.x =1.0f;
 s.center.y =2.0f;
 s.bounding.width =3.0;
 s.bounding.height =4.0;
 s.color = COLOR_GREEN;
 s.values[0] =0.1f;

 cJSON *root = cJSON_CreateObject();
 myTestStruct_to_json(&s, root);
 char *json_str = cJSON_Print(root);
 printf("%s\n", json_str);

 myTestStruct s2 = {0};
 cJSON *parsed = cJSON_Parse(json_str);
 myTestStruct_from_json(&s2, parsed);

 cJSON_Delete(root);
 cJSON_Delete(parsed);
 free(json_str);
 return0;
}
```

## Command-Line Reference

### extract_layout.py

Extracts struct layout information from PDB files.

```bash
python extract_layout.py <pdb_path> <struct_name>
```

**Arguments:**
- `pdb_path` - Path to the PDB file containing debug symbols
- `struct_name` - Name of the root struct to extract

**Output:** JSON to stdout containing all types and dependencies

### generate_c_wrappers.py

Generates C serialization wrapper code from struct layout JSON.

```bash
python generate_c_wrappers.py --root <struct> --in <json_file> [<json_file2> ...] --out-base <basename>
```

**Arguments:**
- `--root <struct>` - Root struct name (optional if only one struct in JSON)
- `--in <json_file>` - Input JSON file(s) with struct layouts
- `--out-base <basename>` - Output file basename (default: `generated_json`)

**Output:** Generates `<basename>.h` and `<basename>.c`

## Supported Types

| Category | Types | Notes |
|----------|-------|-------|
| **Primitives** | `int`, `unsigned int`, `float`, `double`, `bool`, `_Bool` | Serialized as numbers / bools |
| **Strings** | `char[N]`, `char*` | Fixed buffer or pointer (caller owns `char*`) |
| **Arrays** | `T[N]` | Fixed-size arrays of supported element types |
| **Enums** | User-defined | Serialized as underlying integer |
| **Structs** | Nested structs | Recursively serialized objects |
| **Pointers** | `char*` | Other pointers not expanded |

## JSON Input Formats

### Multi-Type Format (Recommended)

```json
{
 "types": {
 "Point": {
 "kind": "struct",
 "size":8,
 "fields": [
 {"name": "x", "type": "float", "offset":0},
 {"name": "y", "type": "float", "offset":4}
 ]
 },
 "Size": {
 "kind": "struct",
 "size":16,
 "fields": [
 {"name": "width", "type": "double", "offset":0},
 {"name": "height", "type": "double", "offset":8}
 ]
 },
 "Color": {
 "kind": "enum",
 "underlying": "int",
 "values": [
 {"name": "COLOR_RED", "value":0},
 {"name": "COLOR_GREEN", "value":1},
 {"name": "COLOR_BLUE", "value":2}
 ]
 },
 "myTestStruct": {
 "kind": "struct",
 "size":48,
 "fields": [
 {"name": "center", "type": "Point", "offset":0},
 {"name": "bounding", "type": "Size", "offset":8},
 {"name": "color", "type": "Color", "offset":24},
 {"name": "values", "type": "float[5]", "offset":28}
 ]
 }
 }
}
```

### Single-Struct Format

```json
{
 "struct": "Point",
 "size":8,
 "fields": [
 {"name": "x", "type": "float", "offset":0},
 {"name": "y", "type": "float", "offset":4}
 ]
}
```

## Encoding Support

Automatically detects file encoding:
- UTF-8 (with or without BOM)
- UTF-16 LE/BE (with BOM)
- UTF-32 LE/BE (with BOM)

## Advanced Usage

### Multiple Input Files

Merge type definitions from multiple JSON files:

```bash
python py_helpers/generate_c_wrappers.py --in core.json extras.json more.json --root myTestStruct --out-base combined
```

### Partial Type Extraction

Generate code for a subset rooted at a struct:

```bash
python py_helpers/generate_c_wrappers.py --in all_types.json --root Point --out-base point_only
```

## Troubleshooting

**Problem:** `UnicodeDecodeError` reading JSON

**Solution:** Ensure file is saved in a supported encoding; auto-detection strips BOM.

**Problem:** Struct not found in PDB

**Solution:** Build with debug symbols (`/Zi`) and verify struct name spelling.

**Problem:** Missing nested type definitions

**Solution:** Use multi-type JSON produced by `extract_layout.py` or merge multiple JSON inputs.

## Contributing

Potential improvements:
- Union support
- Pointer graph expansion options
- Additional output targets (XML, YAML, protobuf)
- Performance tuning for very large type graphs

## License

Provided as-is for educational and commercial use.

## Acknowledgments

- Microsoft DIA SDK
- Dave Gamble's cJSON library

---

