#!/usr/bin/env python3
"""
struct_c_to_from_json.py

Reads settings from a config.ini file and orchestrates the two helper
scripts (extract_layout.py and generate_c_wrappers.py) to emit the C
serialization helpers for a given struct.

Expected config layout:

    [extract]
    pdb_path = ..\\x64\\Debug\\mytest.pdb
    struct_name = myTestStruct
    layout_json = mystruct.json        ; optional, defaults to <struct>.json

    [generate]
    out_base = out/myTestStruct_serial ; optional, defaults to <struct>_serial
    root_struct = myTestStruct         ; optional, defaults to struct_name

All relative paths are resolved relative to the location of the config file.
"""

import argparse
import configparser
import os
import subprocess
import sys
from typing import Optional


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
    layout_json: str,
    root_struct: str,
    out_base: str,
) -> None:
    print(f"[generate] Emitting wrappers for root struct '{root_struct}' using {layout_json}")
    out_dir = os.path.dirname(out_base)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [
        python_exe,
        script_path,
        "--in",
        layout_json,
        "--root",
        root_struct,
        "--out-base",
        out_base,
    ]
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

    struct_name = require_option(cfg, "extract", "struct_name")
    pdb_path_raw = require_option(cfg, "extract", "pdb_path")
    pdb_path = resolve_path(pdb_path_raw, config_dir)
    if not os.path.isfile(pdb_path):
        raise SystemExit(f"PDB file does not exist: {pdb_path}")

    layout_default = f"{struct_name}.json"
    layout_raw = cfg.get("extract", "layout_json", fallback=layout_default).strip() or layout_default
    layout_json = resolve_path(layout_raw, config_dir)

    root_struct = cfg.get("generate", "root_struct", fallback=struct_name).strip() or struct_name
    out_base_default = f"{root_struct}_serial"
    out_base_raw = cfg.get("generate", "out_base", fallback=out_base_default).strip() or out_base_default
    out_base = resolve_path(out_base_raw, config_dir)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    extract_script = os.path.join(script_dir, "extract_layout.py")
    generate_script = os.path.join(script_dir, "generate_c_wrappers.py")
    for script in (extract_script, generate_script):
        if not os.path.isfile(script):
            raise SystemExit(f"Required helper script not found: {script}")

    run_extract(args.python_exe, extract_script, pdb_path, struct_name, layout_json)
    run_generate(args.python_exe, generate_script, layout_json, root_struct, out_base)
    print("[done] Struct serialization helpers generated successfully.")


if __name__ == "__main__":
    main()
