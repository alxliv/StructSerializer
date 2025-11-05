#!/usr/bin/env python3
"""
extract_layout.py

Uses DIA SDK (via pydia2) to open a PDB file, find a struct (myTestStruct),
and dump layout metadata as JSON.
"""

import sys
import json
import pydia2


def load_pdb(pdb_path):
    source = pydia2.CreateObject(pydia2.dia.DiaSource, interface=pydia2.dia.IDiaDataSource)
    source.loadDataFromPdb(pdb_path)
    session = source.openSession()
    return session


def find_udt(session, name):
    global_scope = session.globalScope
    enum = global_scope.findChildren(pydia2.dia.SymTagUDT, name,0)
    for sym_unk in enum:
        sym = sym_unk.QueryInterface(pydia2.dia.IDiaSymbol)
        if sym.name == name:
            return sym
    return None


# Some environments don't publish these enum values via comtypes; provide numeric fallbacks
LocIsThisRel = getattr(pydia2.dia, "LocIsThisRel",4)
LocIsBitField = getattr(pydia2.dia, "LocIsBitField",6)

# DIA BasicType enum fallbacks (https://learn.microsoft.com/windows/win32/api/dia2.h/ne-dia2-basictype)
BT_MAP = {
 getattr(pydia2.dia, "btVoid",1): "void",
 getattr(pydia2.dia, "btChar",2): "char",
 getattr(pydia2.dia, "btWChar",3): "wchar_t",
 getattr(pydia2.dia, "btInt",6): "int",
 getattr(pydia2.dia, "btUInt",7): "unsigned int",
 getattr(pydia2.dia, "btFloat",8): "float",
 getattr(pydia2.dia, "btBCD",9): "BCD",
 getattr(pydia2.dia, "btBool",10): "bool",
 getattr(pydia2.dia, "btLong",13): "long",
 getattr(pydia2.dia, "btULong",14): "unsigned long",
 getattr(pydia2.dia, "btCurrency",25): "CURRENCY",
 getattr(pydia2.dia, "btDate",26): "DATE",
 getattr(pydia2.dia, "btVariant",27): "VARIANT",
 getattr(pydia2.dia, "btComplex",28): "complex",
 getattr(pydia2.dia, "btBit",29): "bit",
 getattr(pydia2.dia, "btBSTR",30): "BSTR",
 getattr(pydia2.dia, "btHresult",31): "HRESULT",
}


def _safe_qi(sym):
    return sym.QueryInterface(pydia2.dia.IDiaSymbol)


def _resolve_type_symbol(t):
    """Return an IDiaSymbol describing the element type for arrays, otherwise the input symbol."""
    t = _safe_qi(t)
    # If this is an array type, return its element type
    try:
        if t.symTag == getattr(pydia2.dia, "SymTagArrayType",0x8):
            elem = t.type
            if elem is not None:
                return _safe_qi(elem)
    except Exception:
        pass
    return t


def _resolve_type_name(t):
    """Return a readable type name for a DIA type symbol, handling arrays and basic types."""
    t = _resolve_type_symbol(t)

    # Prefer the DIA-provided name if present
    try:
        if t.name:
            return t.name
    except Exception:
        pass

    # Fall back to BasicType for compiler intrinsic types (e.g., float, int)
    try:
        bt = t.baseType
        if bt in BT_MAP:
            return BT_MAP[bt]
    except Exception:
        pass

    # As a last resort, return empty string
    return ""


def get_fields(udt):
    fields = []
    for f_unk in udt.findChildren(pydia2.dia.SymTagData, None,0):
        f = _safe_qi(f_unk)
        # Only direct members (non-static)
        if f.locationType in (LocIsThisRel, LocIsBitField):
            type_sym = _safe_qi(f.type)
            fields.append({
                "name": f.name,
                "type": _resolve_type_name(type_sym),
                "offset": f.offset,
                # Use the original type symbol length to capture array size (not the element length)
                "size": getattr(type_sym, "length",0),
            })
    return fields


def main():
    if len(sys.argv) !=3:
        print("Usage: extract_layout.py <pdb_path> <struct_name>")
        sys.exit(1)

    pdb_path = sys.argv[1]
    struct_name = sys.argv[2]

    session = load_pdb(pdb_path)
    udt = find_udt(session, struct_name)
    if udt is None:
        print(f"Struct {struct_name} not found in PDB")
        sys.exit(1)

    layout = {
        "struct": struct_name,
        "size": udt.length,
        "fields": get_fields(udt)
    }

    print(json.dumps(layout, indent=4))


if __name__ == "__main__":
    main()
