#!/usr/bin/env python3
"""
extract_layout.py (single-struct with dependencies)

Enumerate a specified struct and its dependent UDTs/enums in a PDB using DIA SDK (via pydia2),
and emit a unified JSON suitable for generate_c_wrappers_from_layout.py.

Usage:
	python extract_layout.py <pdb_path> <struct_name>
Example:
	python extract_layout.py ..\x64\Debug\mytest.pdb myTestStruct > mystruct.json
"""

import sys
import json
import enum
import pydia2

# --- DIA constants fallbacks / normalization ---
LocIsThisRel = getattr(pydia2.dia, "LocIsThisRel",4)
LocIsBitField = getattr(pydia2.dia, "LocIsBitField",6)


def _dia_tag(name: str, fallback: int) -> int:
	"""Return an int SymTag value robustly across pydia2 variants."""
	val = getattr(pydia2.dia, name, None)
	if val is None:
		return fallback
	try:
		# If it's already an Enum member (e.g., SymTagEnum.SymTagEnum)
		if isinstance(val, enum.Enum):
			return int(val.value)
		# If it's an Enum class (EnumType), fetch member with same name
		if isinstance(val, type) and issubclass(val, enum.Enum):
			member = getattr(val, name, None)
			if member is not None:
				return int(member.value)
		# Else try to coerce to int directly (covers plain ints)
		if isinstance(val, int):
			return val
		return fallback
	except Exception:
		return fallback


SYM_TAG_UDT = _dia_tag("SymTagUDT",11)
SYM_TAG_ENUM = _dia_tag("SymTagEnum",12)
SYM_TAG_DATA = _dia_tag("SymTagData",7)
SYM_TAG_ARRAY_TYPE = _dia_tag("SymTagArrayType",8)
SYM_TAG_TYPEDEF = _dia_tag("SymTagTypedef",13)
SYM_TAG_POINTER_TYPE = _dia_tag("SymTagPointerType",14)


def _bt(name: str, fallback: int) -> int:
	"""Return an int basic type value robustly across pydia2 variants."""
	val = getattr(pydia2.dia, name, None)
	if val is None:
		return fallback
	try:
		if isinstance(val, enum.Enum):
			return int(val.value)
		return int(val)
	except Exception:
		return fallback


BT_MAP = {
	_bt("btVoid",1): "void",
	_bt("btChar",2): "char",
	_bt("btWChar",3): "wchar_t",
	_bt("btInt",6): "int",
	_bt("btUInt",7): "unsigned int",
	_bt("btFloat",8): "float",
	_bt("btBool",10): "bool",
	_bt("btLong",13): "long",
	_bt("btULong",14): "unsigned long",
	_bt("btDouble",16): "double",
}


def safe_qi(sym):
	return sym.QueryInterface(pydia2.dia.IDiaSymbol)


def load_pdb(pdb_path):
	src = pydia2.CreateObject(pydia2.dia.DiaSource, interface=pydia2.dia.IDiaDataSource)
	src.loadDataFromPdb(pdb_path)
	sess = src.openSession()
	return sess


def basic_type_name(sym):
	"""Return a readable basic type name for a DIA type symbol or its declared name."""
	try:
		bt = sym.baseType
		if bt in BT_MAP:
			name = BT_MAP[bt]
			if name == "float":
				try:
					length = getattr(sym, "length", None)
				except Exception:
					length = None
				if length == 8:
					return "double"
			return name
	except Exception:
		pass
	try:
		n = getattr(sym, "name", None)
		if n:
			return n
	except Exception:
		pass
	return "unknown"


def unwrap_alias_array_ptr(t):
	"""Unwrap typedefs, arrays (to element), and pointers (to pointee) to the underlying element type symbol."""
	t = safe_qi(t)
	seen =0
	while seen <16:
		tag = int(getattr(t, "symTag", -1))
		if tag in (SYM_TAG_TYPEDEF, SYM_TAG_ARRAY_TYPE, SYM_TAG_POINTER_TYPE):
			try:
				inner = getattr(t, "type", None)
				if inner is None:
					return t
				t = safe_qi(inner)
				seen +=1
				continue
			except Exception:
				return t
		break
	return t


def resolve_type_name(t):
	"""Return readable type, including arrays (e.g., 'float[5]') and pointers ('T*')."""
	t = safe_qi(t)
	try:
		tag = int(getattr(t, "symTag", -1))
		if tag == SYM_TAG_ARRAY_TYPE:
			elem = safe_qi(t.type)
			elem_name = basic_type_name(unwrap_alias_array_ptr(elem))
			count = getattr(t, "count",0)
			if not count:
				# derive count from lengths if available
				try:
					el_len = getattr(unwrap_alias_array_ptr(elem), "length",0) or 0
					arr_len = getattr(t, "length",0) or 0
					if el_len:
						count = arr_len // el_len
				except Exception:
					pass
			return f"{elem_name}[{count}]"
		if tag == SYM_TAG_POINTER_TYPE:
			inner = safe_qi(t.type)
			name = basic_type_name(unwrap_alias_array_ptr(inner))
			return f"{name}*"
		if tag == SYM_TAG_TYPEDEF:
			# Prefer typedef's own name
			n = getattr(t, "name", None)
			if n:
				return n
	except Exception:
		pass
	return basic_type_name(t)


def get_struct_fields(udt):
	fields = []
	for f_unk in udt.findChildren(SYM_TAG_DATA, None,0):
		f = safe_qi(f_unk)
		if f.locationType in (LocIsThisRel, LocIsBitField):
			type_sym = safe_qi(f.type)
			fields.append({
				"name": f.name,
				"type": resolve_type_name(type_sym),
				"offset": getattr(f, "offset",0),
				"size": getattr(type_sym, "length",0),
			})
	return fields


def find_udt_by_name(session, name):
	gs = session.globalScope
	for s_unk in gs.findChildren(SYM_TAG_UDT, name,0):
		s = safe_qi(s_unk)
		if getattr(s, "name", None) == name:
			return s
	return None


def collect_dependencies_from_udt(udt):
	"""Return a set of dependent type names (UDTs and Enums) referenced by the fields of udt."""
	deps = set()
	for f_unk in udt.findChildren(SYM_TAG_DATA, None,0):
		f = safe_qi(f_unk)
		if f.locationType not in (LocIsThisRel, LocIsBitField):
			continue
		t = safe_qi(f.type)
		base = unwrap_alias_array_ptr(t)
		try:
			tag = int(getattr(base, "symTag", -1))
			if tag in (SYM_TAG_UDT, SYM_TAG_ENUM):
				n = getattr(base, "name", None)
				if n:
					deps.add((tag, n))
		except Exception:
			pass
	return deps


def extract_struct_with_deps(session, root_name):
	result = {"types": {}}
	queue = []
	seen = set()

	root = find_udt_by_name(session, root_name)
	if not root:
		raise RuntimeError(f"Struct {root_name} not found in PDB")

	queue.append((SYM_TAG_UDT, root_name))

	# Pre-collect global enumerators per name for quick lookup
	gs = session.globalScope

	def _find_enum_by_name(name: str):
		for e_unk in gs.findChildren(SYM_TAG_ENUM, name,0):
			e = safe_qi(e_unk)
			if getattr(e, "name", None) == name:
				return e
		return None

	while queue:
		tag, name = queue.pop(0)
		if (tag, name) in seen:
			continue
		seen.add((tag, name))

		if tag == SYM_TAG_UDT:
			udt = find_udt_by_name(session, name)
			if not udt:
				continue
			result["types"][name] = {
				"kind": "struct",
				"size": getattr(udt, "length",0),
				"fields": get_struct_fields(udt),
			}
			for dep_tag, dep_name in collect_dependencies_from_udt(udt):
				if (dep_tag, dep_name) not in seen:
					queue.append((dep_tag, dep_name))
		elif tag == SYM_TAG_ENUM:
			enum_sym = _find_enum_by_name(name)
			if not enum_sym:
				continue
			base = "int"
			try:
				base_sym = safe_qi(enum_sym.type)
				base = basic_type_name(base_sym)
			except Exception:
				pass
			values = []
			for val_unk in enum_sym.findChildren(SYM_TAG_DATA, None,0):
				val = safe_qi(val_unk)
				values.append({
					"name": getattr(val, "name", ""),
					"value": getattr(val, "value",0),
				})
			result["types"][name] = {
				"kind": "enum",
				"underlying": base,
				"values": values,
			}

	return result


def main():
	if len(sys.argv) !=3:
		print("Usage: extract_layout.py <pdb_path> <struct_name>")
		sys.exit(1)

	pdb_path = sys.argv[1]
	root_struct = sys.argv[2]

	session = load_pdb(pdb_path)
	result = extract_struct_with_deps(session, root_struct)
	print(json.dumps(result, indent=4))


if __name__ == "__main__":
	main()
