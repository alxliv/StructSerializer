# StructSerializer

Automatically generates JSON serialization/deserialization C code from PDB debug symbols.
## Overview

StructSerializer extracts C++ struct layout information from PDB files using the Debug Interface Access (DIA) SDK and generates type-safe C serialization wrappers that work with the [cJSON](https://github.com/DaveGamble/cJSON) library. This eliminates the need to manually write tedious serialization code for complex nested structures.

## Features

- **Automatic Type Discovery** - Extracts struct layouts, nested dependencies, and enums from PDB files
- **Full Type Support** - Handles primitives, arrays, nested structs, enums, and pointers
- **Dependency Resolution** - Automatically includes all dependent types in topological order
- **Type-Safe Generation** - Generates strongly-typed C functions for each struct
- **Multi-Format JSON Input** - Supports both single-struct and multi-type JSON formats
- **Encoding-Aware** - Automatically detects and handles UTF-8, UTF-16, and UTF-32 encoded files

## Project structure

```
StructSerializer/
├─ py_helpers/
│  ├─ extract_layout.py          # PDB → JSON (invoked by orchestrator)
│  ├─ generate_c_wrappers.py     # JSON → C code generation logic
│  ├─ struct_c_to_from_json.py   # Orchestrator: PDB → JSON → C
│  └─ config.ini                 # Configuration
└─ README.md
```

## Quick Start

1) Build your project with debug symbols to produce a PDB (Visual Studio: /Zi, Debug configuration).

```bash
cl /Zi /EHsc myproject\your_file.cpp /Fe:app.exe
```

2) Prepare config.ini:

```ini
[extract]
pdb_path = ..\\x64\\Debug\\mytest.pdb      ; MSVC-generated PDB
structs = MyTestStruct, AnotherTestStruct   ; Comma-separated list of root structs

[generator]
# Optional
encoding = auto                       ; auto, utf-8, utf-16, utf-32
emit_helpers = true                   ; emit small helper utilities
pretty_print = true                   ; formatting hints for generated C

[c]
header_guard = AUTOGEN_TO_FROM_JSON_H ; custom include guard
include_cjson = cJSON.h               ; header name/path for cJSON
fn_prefix =                           ; prefix for generated functions (e.g., ss_)
```

3) Run the orchestrator (it will extract from PDB and generate code in one step):

```bash
python py_helpers\struct_c_to_from_json.py --config py_helpers\config.ini
```

This generates:
- autogen_to_from_json.h
- autogen_to_from_json.c

4) Use generated code:
```c
#include "autogen_to_from_json.h"
#include <cjson/cJSON.h>
#include <stdio.h>

int main(void) {
    myTestStruct s = {0};
    // ... populate s ...
    cJSON* obj = cJSON_CreateObject();
    myTestStruct_to_json(&s, obj);
    char* text = cJSON_PrintUnformatted(obj);
    puts(text);

    myTestStruct s2 = {0};
    cJSON* parsed = cJSON_Parse(text);
    myTestStruct_from_json(&s2, parsed);

    cJSON_Delete(parsed);
    cJSON_Delete(obj);
    free(text);
    return 0;
}
```

## Usage

- Run with config file (orchestrates extraction + generation):
  - python py_helpers\struct_c_to_from_json.py --config py_helpers\config.ini
- Override config on command line:
  - python py_helpers\struct_c_to_from_json.py --config config.ini --pdb path\to\app.pdb --root RootType

Outputs (always):
- autogen_to_from_json.h
- autogen_to_from_json.c

## Supported types

- Primitives: int, unsigned, float, double, bool/_Bool
- Enums: serialized as underlying integer
- Arrays: T[N]
- Structs: nested structs (recursive)
- Strings:
  - char[N]: emitted as string (truncated at first '\0')
  - char*: pointer treated as string (assumed UTF-8)
- Unsupported: unions, function pointers, arbitrary non-char pointers

Notes:
- Bitfields may be exposed as underlying integral storage if present in the input.
- Only fixed-size arrays supported (no VLA).

## Requirements

- Windows with Visual Studio 2015+ (to produce PDBs with /Zi)
- Python 3.6+
- pydia2 (DIA bindings) for extract_layout.py: pip install pydia2
- cJSON available to your C build (add cJSON.c to your project, include cJSON.h)

## config.ini reference

[extract]
- pdb_path: Path to the MSVC-generated PDB (string, required)
- structs: Comma-separated list of root struct names (string, required)

[generator]
- encoding: auto|utf-8|utf-16|utf-32 (optional, default auto)
- emit_helpers: true|false (optional)
- pretty_print: true|false (optional)

[c]
- header_guard: Custom guard (optional; default: AUTOGEN_TO_FROM_JSON_H)
- include_cjson: Header to include for cJSON (default: cJSON.h)
- fn_prefix: Prefix for all generated function names (optional)

## Troubleshooting

- PDB/DIA load issues: Ensure matching bitness (x64 Python for x64 PDB), install VS “C++ profiling tools / Windows SDK / DIA SDK” components, and verify the PDB path is correct.
- Missing types in output JSON: Confirm the correct root struct names and that the PDB was built from sources that define them (clean/rebuild with /Zi).
- Mismatched field offsets/sizes: Regenerate the type JSON to match current headers.
- Encoding errors: Set encoding in config.ini or save JSON files in UTF-8.
- Duplicate type names across files: Merge or ensure consistent definitions before generation.

## License

Provided as-is for educational and commercial use.

---

