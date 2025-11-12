#!/usr/bin/env python3
"""
generate_c_wrappers.py

Read DIA-generated layout JSON and emit C wrappers (using cJSON) that
serialize/deserialize the given root struct and any nested structs.

Input JSON formats supported:

A) Preferred multi-type map:
{
 "types": {
 "Point": {
 "kind": "struct",
 "size":8,
 "fields": [
 {"name":"x","type":"float","offset":0},
 {"name":"y","type":"float","offset":4}
 ]
 },
 "Size": {...},
 "Color": {"kind":"enum","underlying":"int"},
 "myTestStruct": {
 "kind":"struct",
 "size": ...,
 "fields":[
 {"name":"center","type":"Point","offset":0},
 {"name":"bounding","type":"Size","offset":8},
 {"name":"color","type":"Color","offset":24},
 {"name":"values","type":"float[5]","offset":28}
 ]
 }
 }
}

B) Minimal single-struct (can pass multiple files to merge):
{
 "struct": "Point",
 "size":8,
 "fields": [ ... ]
}

Usage:
 python generate_c_wrappers.py --root myTestStruct --root OtherStruct \
 --in layout_all.json \
 --out-base combined_serial
Example:
 python generate_c_wrappers.py --root myTestStruct --in mystruct.json --out-base myTestStruct_serial

Outputs:
 <out-base>.h and <out-base>.c
 (default base: "generated_json")
"""

import argparse
import json
import os
import re
from collections import OrderedDict, defaultdict, deque

PRIMS = {"int", "unsigned int", "unsigned long", "float", "double", "bool", "_Bool"}


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", nargs="+", required=True,
                    help="Input JSON file(s) from DIA layout (multi-type or single-struct).")
    ap.add_argument("--root", dest="roots", action="append",
                    help="Root struct name (repeat to export multiple roots; defaults to only struct if unique).")
    ap.add_argument("--out-base", default="generated_json",
                    help="Basename for outputs (default: generated_json).")
    return ap.parse_args()


def load_json_auto(path):
    # Minimal BOM detection
    with open(path, "rb") as fb:
        head = fb.read(4)
        if head.startswith(b"\xEF\xBB\xBF"):
            enc = "utf-8-sig" # strip UTF-8 BOM
        elif head.startswith(b"\xFF\xFE\x00\x00") or head.startswith(b"\x00\x00\xFE\xFF"):
            enc = "utf-32" # auto-handle BOM and endianness
        elif head.startswith(b"\xFF\xFE") or head.startswith(b"\xFE\xFF"):
            enc = "utf-16" # auto-handle BOM and endianness
        else:
            enc = "utf-8"
    with open(path, "r", encoding=enc) as fh:
        return json.load(fh)


def load_types(files):
    types = OrderedDict()
    for f in files:
        data = load_json_auto(f)
        if "types" in data:
            for name, tdef in data["types"].items():
                types[name] = tdef
        elif "struct" in data and "fields" in data:
            name = data["struct"]
            tdef = {"kind": "struct", "size": data.get("size"), "fields": data["fields"]}
            types[name] = tdef
        else:
            raise ValueError(f"{f}: JSON not recognized (needs 'types' or 'struct').")
    for k, v in list(types.items()):
        v.setdefault("kind", "struct")
    return types


def is_array_type(type_str):
    # matches foo[5], char[32], Point[4], etc.
    return bool(re.search(r"\[\s*\d+\s*\]$", type_str))


def array_elem_and_count(type_str):
    m = re.search(r"^(.*)\[\s*(\d+)\s*\]$", type_str)
    if not m:
        return None, None
    elem = m.group(1).strip()
    count = int(m.group(2))
    return elem, count


def is_char_array(type_str):
    # strictly "char[N]"
    elem, count = array_elem_and_count(type_str) if is_array_type(type_str) else (None, None)
    return (elem == "char") and (count is not None)


def is_char_ptr(type_str):
    # "char*" or "char *"
    return type_str.replace(" ", "") == "char*"


def is_primitive(type_str):
    return type_str in PRIMS


def is_enum(types, type_str):
    t = types.get(type_str)
    return bool(t and t.get("kind") == "enum")


def is_struct(types, type_str):
    t = types.get(type_str)
    return bool(t and t.get("kind") == "struct")


def collect_struct_dependency_graph(types):
    """
    Build a graph of struct dependencies so we can order generation.
    Only structs appear as graph nodes. Edges A->B when A has field of struct B or array of struct B.
    """
    graph = defaultdict(set)
    for name, tdef in types.items():
        if tdef.get("kind") != "struct":
            continue
        for fld in tdef.get("fields", []):
            ftype = fld["type"]
            base = ftype
            if is_array_type(ftype):
                base, _ = array_elem_and_count(ftype)
            if is_struct(types, base):
                graph[name].add(base)
            else:
                graph[name] = graph.get(name, set()) # ensure present
    return graph


def topo_order_structs(types, roots=None):
    """
    Topologically order structs so that dependencies are emitted first.
    If roots provided, include only those reachable from the specified roots.
    """
    graph = collect_struct_dependency_graph(types)

    roots_list = []
    if roots:
        if isinstance(roots, str):
            roots_list = [roots]
        else:
            roots_list = list(roots)

    # Limit to reachable if roots specified
    if roots_list:
        reachable = set()
        q = deque(roots_list)
        while q:
            cur = q.popleft()
            if cur in reachable:
                continue
            reachable.add(cur)
            for dep in graph.get(cur, []):
                q.append(dep)
        # Ensure all roots appear even if they have no dependencies
        for root_name in roots_list:
            if root_name in types and types[root_name].get("kind") == "struct":
                reachable.add(root_name)
                graph.setdefault(root_name, set())
        # Filter graph to reachable
        graph = {k: {d for d in v if d in reachable} for k, v in graph.items() if k in reachable}

    # Kahn's algorithm
    indeg = {k:0 for k in graph.keys()}
    for k, vs in graph.items():
        for v in vs:
            indeg[v] = indeg.get(v,0) +1
    q = deque([k for k, deg in indeg.items() if deg ==0])
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for d in graph.get(n, []):
            indeg[d] -=1
            if indeg[d] ==0:
                q.append(d)

    # There may be structs not in graph (no deps and not referenced)
    # include them if no roots were provided
    if not roots_list:
        rest = [k for k in types.keys() if types[k].get("kind") == "struct" and k not in order]
        order.extend(rest)

    if roots_list:
        root_set = set(roots_list)
        # Remove roots for reordering
        non_roots = [s for s in order if s not in root_set]
        ordered_roots = [r for r in roots_list if r in order]
        order = non_roots + ordered_roots

    return order


def gen_decl_name(sname): # function base names
    return sname


def emit_header_decls_for_roots(roots):
    out = []
    out.append("/* Auto-generated: public API */")
    for idx, root in enumerate(roots):
        out.append(f"void {root}_to_json(const {root} *s, cJSON *obj);")
        out.append(f"void {root}_from_json({root} *s, const cJSON *obj);")
        out.append(f"int {root}_equals(const {root} *a, const {root} *b);")
        if idx != len(roots) -1:
            out.append("")
    out.append("")
    return "\n".join(out)


def emit_to_json_for_field(types, fname, ftype):
    code = []
    # char[N] as string
    if is_char_array(ftype):
        code.append(f'\tcJSON_AddStringToObject(obj, "{fname}", s->{fname});')
        return code

    # char* as string (nullable)
    if is_char_ptr(ftype):
        code.append(f'\tcJSON_AddStringToObject(obj, "{fname}", s->{fname} ? s->{fname} : "");')
        return code

    # Array?
    if is_array_type(ftype):
        elem, count = array_elem_and_count(ftype)
        code.append("\t{ cJSON *arr = cJSON_CreateArray();")
        code.append(f"\t\tfor (int i =0; i < {count}; ++i) {{")
        if is_primitive(elem) or is_enum(types, elem):
            # numbers/bools/enums
            add = "Number" # cJSON only has Number
            cast = "(double)" if elem in {"float", "double"} else ""
            code.append(f"\t\t\tcJSON_AddItemToArray(arr, cJSON_Create{add}({cast}s->{fname}[i]));")
        elif is_struct(types, elem):
            code.append("\t\t\tcJSON *child = cJSON_CreateObject();")
            code.append(f"\t\t\t{elem}_to_json(&s->{fname}[i], child);")
            code.append("\t\t\tcJSON_AddItemToArray(arr, child);")
        else:
            code.append(f"\t\t\t/* Unsupported array elem type: {elem} */")
        code.append("\t\t}")
        code.append(f'\t\tcJSON_AddItemToObject(obj, "{fname}", arr);')
        code.append("\t}")
        return code

    # Primitive?
    if is_primitive(ftype) or is_enum(types, ftype):
        # bool/_Bool can still be emitted with Number; or use True/False
        if ftype in {"bool", "_Bool"}:
            code.append(f'\tcJSON_AddBoolToObject(obj, "{fname}", s->{fname} ?1 :0);')
        elif ftype in {"float", "double"}:
            code.append(f'\tcJSON_AddNumberToObject(obj, "{fname}", (double)s->{fname});')
        else:
            code.append(f'\tcJSON_AddNumberToObject(obj, "{fname}", s->{fname});')
        return code

    # Nested struct?
    if is_struct(types, ftype):
        code.append("\t{ cJSON *child = cJSON_CreateObject();")
        code.append(f"\t\t{ftype}_to_json(&s->{fname}, child);")
        code.append(f'\t\tcJSON_AddItemToObject(obj, "{fname}", child);')
        code.append("\t}")
        return code

    code.append(f"\t/* Unsupported field type: {ftype} */")
    return code


def emit_from_json_for_field(types, fname, ftype):
    code = []
    # char[N] as string
    if is_char_array(ftype):
        code.append(f'\t{{ const cJSON *tmp = cJSON_GetObjectItem(obj, "{fname}");')
        code.append("\t\tif (tmp && cJSON_IsString(tmp) && tmp->valuestring) {")
        code.append(f"\t\t\tstrncpy(s->{fname}, tmp->valuestring, sizeof(s->{fname}) -1);")
        code.append(f"\t\t\ts->{fname}[sizeof(s->{fname}) -1] = '\\0';")
        code.append("\t\t}")
        code.append("\t}")
        return code

    # char* as string
    if is_char_ptr(ftype):
        code.append(f'\t{{ const cJSON *tmp = cJSON_GetObjectItem(obj, "{fname}");')
        code.append("\t\tif (tmp && cJSON_IsString(tmp) && tmp->valuestring) {")
        code.append("\t\t\t/* NOTE: caller should free previous pointer if needed */")
        code.append(f"\t\t\ts->{fname} = _strdup(tmp->valuestring);")
        code.append("\t\t}")
        code.append("\t}")
        return code

    # Array?
    if is_array_type(ftype):
        elem, count = array_elem_and_count(ftype)
        code.append(f'\t{{ const cJSON *arr = cJSON_GetObjectItem(obj, "{fname}");')
        code.append("\t\tif (arr && cJSON_IsArray(arr)) {")
        code.append("\t\t\tint idx =0;")
        code.append("\t\t\tcJSON *el = NULL;")
        code.append("\t\t\tcJSON_ArrayForEach(el, arr) {")
        code.append(f"\t\t\t\tif (idx >= {count}) break;")
        if is_primitive(elem) or is_enum(types, elem):
            if elem == "float":
                code.append(f"\t\t\t\ts->{fname}[idx++] = (float)el->valuedouble;")
            elif elem == "double":
                code.append(f"\t\t\t\ts->{fname}[idx++] = (double)el->valuedouble;")
            elif elem in {"bool", "_Bool"}:
                code.append(f"\t\t\t\ts->{fname}[idx++] = (el->type == cJSON_True) ?1 : (el->valueint !=0);")
            else:
                code.append(f"\t\t\t\ts->{fname}[idx++] = el->valueint;")
        elif is_struct(types, elem):
            code.append(f"\t\t\t\tif (cJSON_IsObject(el)) {elem}_from_json(&s->{fname}[idx++], el);")
        else:
            code.append(f"\t\t\t\t/* Unsupported array elem type: {elem} */")
        code.append("\t\t\t}")
        code.append("\t\t}")
        code.append("\t}")
        return code

    # Primitive / enum?
    if is_primitive(ftype) or is_enum(types, ftype):
        code.append(f'\t{{ const cJSON *tmp = cJSON_GetObjectItem(obj, "{fname}");')
        code.append("\t\tif (tmp) {")
        if ftype in {"float", "double"}:
            cast = "(float)" if ftype == "float" else "(double)"
            code.append(f"\t\t\ts->{fname} = {cast}tmp->valuedouble;")
        elif ftype in {"bool", "_Bool"}:
            code.append(f"\t\t\ts->{fname} = (tmp->type == cJSON_True) ?1 : (tmp->valueint !=0);")
        else:
            code.append(f"\t\t\ts->{fname} = tmp->valueint;")
        code.append("\t\t}")
        code.append("\t}")
        return code

    # Nested struct?
    if is_struct(types, ftype):
        code.append(f'\t{{ const cJSON *child = cJSON_GetObjectItem(obj, "{fname}");')
        code.append(f"\t\tif (child && cJSON_IsObject(child)) {ftype}_from_json(&s->{fname}, child);")
        code.append("\t}")
        return code

    code.append(f"\t/* Unsupported field type: {ftype} */")
    return code


def emit_equals_for_field(types, fname, ftype):
    code = []
    if is_char_array(ftype):
        code.append(f"\tif (memcmp(a->{fname}, b->{fname}, sizeof(a->{fname})) != 0) return 0;")
        return code

    if is_char_ptr(ftype):
        code.append(f"\tif ((a->{fname} ?1:0) != (b->{fname} ?1:0)) return 0;")
        code.append(f"\tif (a->{fname} && strcmp(a->{fname}, b->{fname}) != 0) return 0;")
        return code

    if is_array_type(ftype):
        elem, count = array_elem_and_count(ftype)
        code.append(f"\tfor (int i = 0; i < {count}; ++i) {{")
        if is_primitive(elem) or is_enum(types, elem):
            if elem == "float":
                code.append(f"\t\tif (fabsf(a->{fname}[i] - b->{fname}[i]) > AUTOGEN_FLOAT_EPSILON) return 0;")
            elif elem == "double":
                code.append(f"\t\tif (fabs(a->{fname}[i] - b->{fname}[i]) > AUTOGEN_DOUBLE_EPSILON) return 0;")
            elif elem in {"bool", "_Bool"}:
                code.append(f"\t\tif ((a->{fname}[i] ?1:0) != (b->{fname}[i] ?1:0)) return 0;")
            else:
                code.append(f"\t\tif (a->{fname}[i] != b->{fname}[i]) return 0;")
        elif is_struct(types, elem):
            code.append(f"\t\tif (!{elem}_equals(&a->{fname}[i], &b->{fname}[i])) return 0;")
        else:
            code.append(f"\t\t/* Unsupported array elem type: {elem} */")
        code.append("\t}")
        return code

    if is_primitive(ftype) or is_enum(types, ftype):
        if ftype == "float":
            code.append(f"\tif (fabsf(a->{fname} - b->{fname}) > AUTOGEN_FLOAT_EPSILON) return 0;")
        elif ftype == "double":
            code.append(f"\tif (fabs(a->{fname} - b->{fname}) > AUTOGEN_DOUBLE_EPSILON) return 0;")
        elif ftype in {"bool", "_Bool"}:
            code.append(f"\tif ((a->{fname} ?1:0) != (b->{fname} ?1:0)) return 0;")
        else:
            code.append(f"\tif (a->{fname} != b->{fname}) return 0;")
        return code

    if is_struct(types, ftype):
        code.append(f"\tif (!{ftype}_equals(&a->{fname}, &b->{fname})) return 0;")
        return code

    code.append(f"\t/* Unsupported field type for equals: {ftype} */")
    return code


def emit_struct_impl(types, sname, public_api=False):
    tdef = types[sname]
    fields = tdef.get("fields", [])
    storage_void = "void" if public_api else "static void"
    storage_int = "int" if public_api else "static int"
    lines = []
    # to_json
    lines.append(f"{storage_void} {sname}_to_json(const {sname} *s, cJSON *obj) {{")
    for fld in fields:
        lines.extend(emit_to_json_for_field(types, fld['name'], fld['type']))
    lines.append("}\n")
    # from_json
    lines.append(f"{storage_void} {sname}_from_json({sname} *s, const cJSON *obj) {{")
    for fld in fields:
        lines.extend(emit_from_json_for_field(types, fld['name'], fld['type']))
    lines.append("}\n")
    # equals
    lines.append(f"{storage_int} {sname}_equals(const {sname} *a, const {sname} *b) {{")
    lines.append("\tif (a == b) return 1;")
    lines.append("\tif (!a || !b) return 0;")
    for fld in fields:
        lines.extend(emit_equals_for_field(types, fld['name'], fld['type']))
    lines.append("\treturn 1;")
    lines.append("}\n")
    return "\n".join(lines)


def emit_struct_prototypes(sname, public_api=False):
    if public_api:
        return ""
    out = []
    out.append(f"static void {sname}_to_json(const {sname} *s, cJSON *obj);")
    out.append(f"static void {sname}_from_json({sname} *s, const cJSON *obj);")
    out.append(f"static int {sname}_equals(const {sname} *a, const {sname} *b);")
    out.append("")
    return "\n".join(out)


def main():
    args = parse_args()
    types = load_types(args.inputs)

    roots = args.roots or []
    if not roots:
        structs = [k for k, v in types.items() if v.get("kind") == "struct"]
        if len(structs) == 1:
            roots = [structs[0]]
        else:
            raise SystemExit("Please pass --root <StructName> (repeatable) when multiple structs are present.")

    dedup_roots = []
    seen_roots = set()
    for root in roots:
        if root not in seen_roots:
            dedup_roots.append(root)
            seen_roots.add(root)
    roots = dedup_roots

    for root in roots:
        if root not in types or types[root].get("kind") != "struct":
            raise SystemExit(f"--root {root} is not a struct present in input types.")

    # Order structs so nested deps are emitted first (and declared)
    order = topo_order_structs(types, roots=roots)
    root_set = set(roots)

    base = args.out_base
    h_path = f"{base}.h"
    c_path = f"{base}.c"

    # Emit header
    h = []
    h.append("#pragma once")
    h.append("#include <string.h>")
    h.append('#include "mytypes.h"')
    h.append('#include "cJSON.h"')

    h.append("")
    h.append("/* Auto-generated by generate_c_wrappers_from_layout.py */")
    h.append("")
    h.append('#ifdef __cplusplus')
    h.append('extern "C" {')
    h.append('#endif')
    h.append("")

    # Only public API for requested roots
    h.append(emit_header_decls_for_roots(roots))
    h.append('#ifdef __cplusplus')
    h.append('} /* extern "C" */')
    h.append('#endif')

    with open(h_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h) + "\n")

    # Emit impl
    c = []
    c.append("/* Auto-generated by generate_c_wrappers_from_layout.py */")
    c.append(f'#include "{os.path.basename(h_path)}"')
    c.append("#include <math.h>")
    c.append("")
    c.append("#ifndef AUTOGEN_FLOAT_EPSILON")
    c.append("#define AUTOGEN_FLOAT_EPSILON 1e-6f")
    c.append("#endif")
    c.append("#ifndef AUTOGEN_DOUBLE_EPSILON")
    c.append("#define AUTOGEN_DOUBLE_EPSILON 1e-9")
    c.append("#endif")
    c.append("")

    prototypes = []
    for sname in order:
        proto = emit_struct_prototypes(sname, public_api=(sname in root_set))
        if proto:
            prototypes.append(proto)
    if prototypes:
        c.append("/* Forward declarations for static helpers */")
        c.extend(prototypes)

    for sname in order:
        c.append(emit_struct_impl(types, sname, public_api=(sname in root_set)))

    with open(c_path, "w", encoding="utf-8") as fc:
        fc.write("\n".join(c) + "\n")

    print(f"Wrote: {h_path}, {c_path}")
    print("Structs emitted (dependency order):")
    for s in order:
        print(" -", s)


if __name__ == "__main__":
    main()
