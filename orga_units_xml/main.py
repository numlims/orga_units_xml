from __future__ import annotations

import argparse
from pathlib import Path

from lxml import etree as ET

from generator import build_xml_documents_from_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate CentraXX OU import XML files from YAML"
    )
    parser.add_argument("db_name", help="CentraXX database name")
    parser.add_argument("--input", required=True, help="Path to YAML input file")
    parser.add_argument(
        "--output-dir", required=True, help="Directory for output XML files"
    )
    parser.add_argument(
        "--prefix",
        default="org_unit_import",
        help="Filename prefix for generated XML files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    docs = build_xml_documents_from_yaml(input_path, args.db_name)

    for key, xml_root in docs.items():
        output_path = output_dir / f"{args.prefix}_{key}.xml"
        output_path.write_bytes(
            ET.tostring(
                xml_root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
            )
        )
        print(f"XML generated: {output_path}")

    return 0


import sys

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
