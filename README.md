# StructSerializer

Python script (**struct_c_to_from_json.py**) that automatically generates JSON serialization/deserialization C code from PDB debug symbols.

## Overview

**struct_c_to_from_json.py** extracts C/C++ struct layout information from PDB files using the Debug Interface Access (DIA) SDK and generates type-safe C serialization wrappers that work with the [cJSON](https://github.com/DaveGamble/cJSON) library. This eliminates the need to manually write tedious serialization code for complex nested structures.

## Features

- **Automatic Type Discovery** - Extracts struct layouts, nested dependencies, and enums from PDB files
- **Full Type Support** - Handles primitives, arrays, nested structs, enums, and pointers
- **Dependency Resolution** - Automatically includes all dependent types in topological order
- **Type-Safe Generation** - Generates strongly-typed C functions for each struct

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

## Prerequisites

### Python Dependencies
- Python3.6+ (I tested with 3.11.9)
- `pydia2` - DIA SDK Python bindings for PDB parsing

Install with:
```bash
pip install pydia2
```

## Quick Start

1) Build your C/C++ project with debug symbols to produce a PDB file (Visual Studio: /Zi, Debug configuration).

```bash
cl /Zi /EHsc myproject\your_file.cpp /Fe:app.exe
```

2) Prepare config.ini:

```ini
[extract]
pdb_path = ..\\x64\\Debug\\mytest.pdb      ; MSVC-generated PDB
structs = myTestStruct, AnotherTestStruct   ; Comma-separated list of root structs

```

3) Run the orchestrator (it will read config.ini and extract from PDB and generate code in one step):

```bash
cd py_helpers
python struct_c_to_from_json.py
```

This generates in *out* folder:
- autogen_to_from_json.h
- autogen_to_from_json.c

4) Use generated code:

**mytypes.h**
```h
#pragma once

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
    Point origin;
    Size size;
} Rect;

typedef struct {
    Point center;
    Size bounding;
    Color color;
    float values[5];
} myTestStruct;

typedef struct {
    unsigned int status;
    char flags;
    Size tt_size;
} SomeTT;

#define NUM_POINTS (4)
typedef struct {
    Point center;
    Size bounding;
    Color color;
    SomeTT some_tt;
    Point points[NUM_POINTS];
} AnotherTestStruct;

```

**mytest.cpp**
```c

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "mytypes.h"
#include "..\py_helpers/out/autogen_to_from_json.h"


int main()
{
    myTestStruct s;
    s.center.x = 1.0f;
    s.center.y = 2.0f;
    s.bounding.width = 3.0;
    s.bounding.height = 4.0;
    s.color = COLOR_GREEN;
    s.values[0] = 0.1f;
    s.values[1] = 0.2f;
    s.values[2] = 0.3f;
    s.values[3] = 0.4f;
    s.values[4] = 0.5f;

    AnotherTestStruct another;
    another.bounding = { 1.34, 5.67 };
    another.center = { 6.78f, 9.0f };
    another.color = COLOR_BLUE;
    another.points[0] = { 1,2 };
    another.points[1] = { 3,4 };
    another.points[2] = { 5,6 };
    another.points[3] = { 7,8 };

    another.some_tt.flags = 0x34;
    another.some_tt.status = 0xabcd;
    another.some_tt.tt_size = { 0.3,0.6 };


#if 1
    cJSON* root = cJSON_CreateObject();

    // Serialize myTestStruct under its own key
    {
        cJSON* s_obj = cJSON_CreateObject();
        myTestStruct_to_json(&s, s_obj);
        cJSON_AddItemToObject(root, "myTestStruct", s_obj);
    }

    // Serialize AnotherTestStruct under its own key
    {
        cJSON* a_obj = cJSON_CreateObject();
        AnotherTestStruct_to_json(&another, a_obj);
        cJSON_AddItemToObject(root, "AnotherTestStruct", a_obj);
    }

    char* json_str = cJSON_Print(root);
    printf("%s\n", json_str);

    cJSON* parsed = cJSON_Parse(json_str);

    myTestStruct s2 = { 0 };
    {
        const cJSON* s_obj = cJSON_GetObjectItem(parsed, "myTestStruct");
        assert(s_obj && cJSON_IsObject(s_obj));
        myTestStruct_from_json(&s2, s_obj);
    }

    AnotherTestStruct a2 = { 0 };
    {
        const cJSON* a_obj = cJSON_GetObjectItem(parsed, "AnotherTestStruct");
        assert(a_obj && cJSON_IsObject(a_obj));
        AnotherTestStruct_from_json(&a2, a_obj);
    }

    cJSON_Delete(root);
    cJSON_Delete(parsed);
    free(json_str);

    assert(myTestStruct_equals(&s, &s2));
    assert(AnotherTestStruct_equals(&another, &a2));
#endif

    printf("all done OK\n");
    return 0;
}


```


## License

This project is licensed under the [MIT License](LICENSE).

---

