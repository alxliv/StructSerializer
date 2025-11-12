#!/usr/bin/env python3
"""
struct_c_to_from_json.py

Reads settings from a config.ini file and orchestrates the two helper
scripts (extract_layout.py and generate_c_wrappers.py) to emit the C
serialization helpers for a given struct.

Expected config layout:

    [extract]
    pdb_path = ..\\x64\\Debug\\mytest.pdb

    [struct:myTestStruct]
    layout_json = layouts\\myTestStruct.json        ; optional, defaults to <struct>.json
    root_struct = myTestStruct                       ; optional, defaults to section name

    [struct:AnotherStruct]
    layout_json = layouts\\AnotherStruct.json
    root_struct = AnotherStruct

All relative paths are resolved relative to the location of the config file.

Generated files are always written to:
    out/autogen_to_from_json.c
    out/autogen_to_from_json.h
"""

import argparse
import configparser
import os
import subprocess
import sys
from typing import List, Set

AUTOGEN_BASE = os.path.join("out", "autogen_to_from_json")
AUTOGEN_C_FILENAME = "autogen_to_from_json.c"
AUTOGEN_H_FILENAME = "autogen_to_from_json.h"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate JSON (de)serialization wrappers for a struct using config.ini."
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config.ini",
        help="Path to the config.ini file (default: ./config.ini).",
    )
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Python interpreter used to run helper scripts (default: current interpreter).",
    )
    return parser.parse_args()


def resolve_path(value: str, base_dir: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(base_dir, expanded))


def ensure_parent_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)


def require_option(cfg: configparser.ConfigParser, section: str, option: str) -> str:
    if not cfg.has_section(section):
        raise SystemExit(f"Config is missing required section [{section}].")
    if not cfg.has_option(section, option):
        raise SystemExit(f"Config option '{option}' is missing from section [{section}].")
    value = cfg.get(section, option).strip()
    if not value:
        raise SystemExit(f"Config option '{option}' in section [{section}] must not be empty.")
    return value


def load_config(path: str) -> configparser.ConfigParser:
    if not os.path.isfile(path):
        raise SystemExit(f"Config file not found: {path}")
    cfg = configparser.ConfigParser(
        inline_comment_prefixes=(";", "#", "'")  # accept ;, #, or ' as inline comments
    )
    if not cfg.read(path):
        raise SystemExit(f"Failed to read config file: {path}")
    return cfg


def run_extract(
    python_exe: str,
    script_path: str,
    pdb_path: str,
    struct_name: str,
    layout_json: str,
) -> None:
    print(f"[extract] Generating layout for struct '{struct_name}' from {pdb_path}")
    ensure_parent_dir(layout_json)
    cmd = [python_exe, script_path, pdb_path, struct_name]
    try:
        with open(layout_json, "w", encoding="utf-8") as output_file:
            subprocess.run(cmd, check=True, text=True, stdout=output_file)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"extract_layout.py failed with exit code {exc.returncode}") from exc
    print(f"[extract] Layout written to {layout_json}")


def run_generate(
    python_exe: str,
    script_path: str,
    layout_jsons: List[str],
    root_structs: List[str],
    out_base: str,
) -> None:
    if not layout_jsons or not root_structs:
        raise SystemExit("Generation requires at least one layout JSON and one root struct name.")
    print(
        f"[generate] Emitting wrappers for {len(root_structs)} struct(s) using {len(layout_jsons)} layout file(s)"
    )
    out_dir = os.path.dirname(out_base)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [python_exe, script_path, "--in"]
    cmd.extend(layout_jsons)
    for root_struct in root_structs:
        cmd.extend(["--root", root_struct])
    cmd.extend(["--out-base", out_base])
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"generate_c_wrappers.py failed with exit code {exc.returncode}") from exc
    print(f"[generate] Completed. Outputs: {out_base}.h / {out_base}.c")


def main() -> None:
    args = parse_args()
    config_path = os.path.abspath(args.config)
    cfg = load_config(config_path)
    config_dir = os.path.dirname(config_path)

    pdb_path_raw = require_option(cfg, "extract", "pdb_path")
    pdb_path = resolve_path(pdb_path_raw, config_dir)
    if not os.path.isfile(pdb_path):
        raise SystemExit(f"PDB file does not exist: {pdb_path}")

    struct_sections = [section for section in cfg.sections() if section.lower().startswith("struct:")]
    if not struct_sections:
        raise SystemExit("Config must define at least one [struct:<name>] section.")

    global_root_override = ""
    if cfg.has_section("generate"):
        global_root_override = cfg.get("generate", "root_struct", fallback="").strip()

    global_layout_hint = ""
    if cfg.has_option("extract", "layout_json"):
        global_layout_hint = cfg.get("extract", "layout_json").strip()

    jobs = []

    for section in struct_sections:
        try:
            _, raw_name = section.split(":", 1)
        except ValueError as exc:
            raise SystemExit(f"Invalid section name '[{section}]'. Expected format [struct:<name>].") from exc
        struct_label = raw_name.strip()
        if not struct_label:
            raise SystemExit(f"Section '[{section}]' must declare a struct name after 'struct:'.")

        struct_name = cfg.get(section, "struct_name", fallback=struct_label).strip() or struct_label

        layout_default = f"{struct_name}.json"
        layout_raw = cfg.get(section, "layout_json", fallback="").strip()
        if not layout_raw:
            layout_raw = global_layout_hint or layout_default
        layout_json = resolve_path(layout_raw, config_dir)

        root_struct = cfg.get(section, "root_struct", fallback="").strip()
        if not root_struct:
            root_struct = global_root_override or struct_name

        jobs.append({
            "struct_name": struct_name,
            "layout_json": layout_json,
            "root_struct": root_struct,
        })

    if not jobs:
        raise SystemExit("No struct definitions resolved from config. Check [struct:<name>] sections.")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    extract_script = os.path.join(script_dir, "extract_layout.py")
    generate_script = os.path.join(script_dir, "generate_c_wrappers.py")
    for script in (extract_script, generate_script):
        if not os.path.isfile(script):
            raise SystemExit(f"Required helper script not found: {script}")

    for job in jobs:
        run_extract(args.python_exe, extract_script, pdb_path, job["struct_name"], job["layout_json"])

    layout_jsons = [job["layout_json"] for job in jobs]
    root_structs: List[str] = []
    seen_roots: Set[str] = set()
    for job in jobs:
        root_struct = job["root_struct"]
        if root_struct not in seen_roots:
            seen_roots.add(root_struct)
            root_structs.append(root_struct)

    out_base = resolve_path(AUTOGEN_BASE, config_dir)
    run_generate(args.python_exe, generate_script, layout_jsons, root_structs, out_base)

    generated_c = f"{out_base}.c"
    generated_h = f"{out_base}.h"
    if not os.path.isfile(generated_c) or not os.path.isfile(generated_h):
        raise SystemExit("Expected generated files were not produced by generate_c_wrappers.py")
    out_dir = os.path.dirname(out_base)
    final_c = os.path.join(out_dir, AUTOGEN_C_FILENAME)
    final_h = os.path.join(out_dir, AUTOGEN_H_FILENAME)

    if generated_c != final_c:
        if os.path.isfile(final_c):
            os.remove(final_c)
        os.replace(generated_c, final_c)

    if generated_h != final_h:
        if os.path.isfile(final_h):
            os.remove(final_h)
        os.replace(generated_h, final_h)

    print(
        f"[done] Generated wrappers for {len(root_structs)} struct(s): {final_c} / {final_h}"
    )


if __name__ == "__main__":
    main()
