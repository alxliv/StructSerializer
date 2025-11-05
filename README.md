# StructSerializer

A powerful C++ struct serialization toolkit that automatically generates JSON serialization/deserialization code from PDB debug symbols.

## Overview

StructSerializer extracts C++ struct layout information from PDB files using the Debug Interface Access (DIA) SDK and generates type-safe C serialization wrappers that work with the [cJSON](https://github.com/DaveGamble/cJSON) library. This eliminates the need to manually write tedious serialization code for complex nested structures.

## Features

- ?? **Automatic Type Discovery** - Extracts struct layouts, nested dependencies, and enums from PDB files
- ?? **Full Type Support** - Handles primitives, arrays, nested structs, enums, and pointers
- ?? **Dependency Resolution** - Automatically includes all dependent types in topological order
- ?? **Type-Safe Generation** - Generates strongly-typed C functions for each struct
- ?? **Multi-Format JSON Input** - Supports both single-struct and multi-type JSON formats
- ?? **Encoding-Aware** - Automatically detects and handles UTF-8, UTF-16, and UTF-32 encoded files

## Project Structure

```
StructSerializer/
??? py_helpers/
?   ??? extract_layout.py  # Extract struct info from PDB files
?   ??? generate_c_wrappers.py    # Generate C serialization code
??? mytest/
?   ??? mytypes.h        # Example C++ struct definitions
?   ??? mytest.cpp      # Example usage
??? README.md
```

## Prerequisites

### Python Dependencies
- Python 3.6+
- `pydia2` - DIA SDK Python bindings for PDB parsing

Install with:
```bash
pip install pydia2
```

### C/C++ Dependencies
- Visual Studio 2015+ (for C++14 support and PDB generation)
- [cJSON library](https://github.com/DaveGamble/cJSON) for JSON operations

## Quick Start

### 1. Define Your Structs

Create your C++ structures with nested types and enums:

```cpp
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
    Point center;
    Size bounding;
    Color color;
    float values[5];
} myTestStruct;
```

### 2. Compile with Debug Symbols

Build your C++ code with debug information enabled to generate a PDB file:

```bash
# Visual Studio: Build in Debug mode or with /Zi flag
cl /Zi mytest.cpp
```

### 3. Extract Struct Layout

Use `extract_layout.py` to parse the PDB and extract struct information:

```bash
python py_helpers/extract_layout.py x64/Debug/mytest.pdb myTestStruct > mystruct.json
```

This generates a JSON file containing the complete type information:

```json
{
  "types": {
    "Point": {
      "kind": "struct",
      "size": 8,
      "fields": [
        {"name": "x", "type": "float", "offset": 0},
     {"name": "y", "type": "float", "offset": 4}
      ]
    },
    "myTestStruct": {
      "kind": "struct",
      "size": 48,
      "fields": [
        {"name": "center", "type": "Point", "offset": 0},
      {"name": "bounding", "type": "Size", "offset": 8},
        {"name": "color", "type": "Color", "offset": 24},
      {"name": "values", "type": "float[5]", "offset": 28}
      ]
    }
  }
}
```

### 4. Generate Serialization Code

Use `generate_c_wrappers.py` to create the serialization functions:

```bash
python py_helpers/generate_c_wrappers.py --root myTestStruct --in mystruct.json --out-base myTestStruct_serial
```

This generates two files:
- `myTestStruct_serial.h` - Function declarations
- `myTestStruct_serial.c` - Function implementations

### 5. Use in Your Code

Include the generated files and use the serialization functions:

```c
#include "myTestStruct_serial.h"

// Serialize struct to JSON
myTestStruct s = { /* ... */ };
cJSON *root = cJSON_CreateObject();
myTestStruct_to_json(&s, root);
char *json_str = cJSON_Print(root);
printf("%s\n", json_str);

// Deserialize JSON to struct
myTestStruct s2;
cJSON *parsed = cJSON_Parse(json_str);
myTestStruct_from_json(&s2, parsed);

// Cleanup
cJSON_Delete(root);
cJSON_Delete(parsed);
free(json_str);
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
python generate_c_wrappers.py --root <struct> --in <json_file> --out-base <basename>
```

**Arguments:**
- `--root <struct>` - Root struct name (optional if only one struct in JSON)
- `--in <json_file>` - Input JSON file(s) with struct layouts (can specify multiple)
- `--out-base <basename>` - Output file basename (default: `generated_json`)

**Output:** Generates `<basename>.h` and `<basename>.c`

## Supported Types

| Category | Types | Notes |
|----------|-------|-------|
| **Primitives** | `int`, `unsigned int`, `float`, `double`, `bool`, `_Bool` | Serialized as JSON numbers/booleans |
| **Strings** | `char[N]`, `char*` | Handled as JSON strings |
| **Arrays** | `T[N]` | Fixed-size arrays of any supported type |
| **Enums** | User-defined | Serialized as integers |
| **Structs** | Nested structs | Recursively serialized as JSON objects |
| **Pointers** | `T*` | Limited support; `char*` for strings |

## JSON Input Formats

The tool supports two JSON input formats:

### Multi-Type Format (Recommended)

```json
{
  "types": {
    "TypeName1": { "kind": "struct", "size": 16, "fields": [...] },
    "TypeName2": { "kind": "enum", "underlying": "int", "values": [...] }
  }
}
```

### Single-Struct Format

```json
{
  "struct": "TypeName",
  "size": 16,
  "fields": [...]
}
```

## Encoding Support

The tool automatically detects file encoding:
- **UTF-8** (with or without BOM)
- **UTF-16 LE/BE** (with BOM)
- **UTF-32 LE/BE** (with BOM)

This ensures compatibility with JSON files generated by various tools and editors.

## Advanced Usage

### Multiple Input Files

Merge type definitions from multiple JSON files:

```bash
python generate_c_wrappers.py --in types1.json types2.json types3.json --root MyStruct --out-base combined
```

### Partial Type Extraction

Generate code for only specific types and their dependencies by specifying `--root`:

```bash
python generate_c_wrappers.py --root Point --in alltypes.json --out-base point_only
```

## Troubleshooting

### Common Issues

**Problem:** `UnicodeDecodeError` when reading JSON files

**Solution:** The tool now automatically detects encoding. If issues persist, ensure your JSON file is saved in UTF-8, UTF-16, or UTF-32 format.

---

**Problem:** "Struct not found in PDB"

**Solution:** Ensure you're building with debug symbols (`/Zi` flag) and the struct name matches exactly (case-sensitive).

---

**Problem:** Missing nested type definitions

**Solution:** The tool automatically includes dependencies. Ensure all types are defined in the PDB or provide multiple input JSON files.

## Contributing

Contributions are welcome! Areas for improvement:
- Support for unions
- Better pointer type handling
- Additional output formats (XML, Protocol Buffers, etc.)
- Performance optimizations for large struct hierarchies

## License

This project is provided as-is for educational and commercial use.

## Acknowledgments

- Uses Microsoft's Debug Interface Access (DIA) SDK
- Integrates with [cJSON](https://github.com/DaveGamble/cJSON) by Dave Gamble
- Inspired by the need for automatic serialization in C++ projects

---

**Built with ?? for developers tired of writing serialization boilerplate**