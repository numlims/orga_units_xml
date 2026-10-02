from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lxml import etree as ET

from orga_units_xml import build_xml_documents_from_yaml


def create_parser() -> argparse.ArgumentParser:
    parser_description = "Generate Centraxx import XML files from a YAML file."
    parser_epilog = (
        "What this script generates:\n"
        "  1) Organisation unit creation XML\n"
        "  2) User assignment XML (users to organisation unit roles)\n"
        "  3) Study release XML (organisation unit release for the study)\n"
        "  4) Storage location XML (storage locations for the organisation unit)\n\n"
        "Usage (installed package):\n"
        "  goe database_name --input templates/file_name.yaml --output-dir output_directory --prefix any_prefix\n\n"
        "Usage (running the script directly):\n"
        "  python -m orga_units_xml.main database_name --input templates/file_name.yaml --output-dir output_directory --prefix any_prefix\n\n"
        "After generating files, import them in Centraxx:\n"
        "  Administration -> Interfaces -> Import\n"
        "  Import the generated XML files in order (as listed in the success output).\n\n"
        "Further information:\n"
        "  Wiki: http://num-etl:5000/wie%20eine%20organisationseinheit%20erstellen"
    )
    parser = argparse.ArgumentParser(
        description=parser_description,
        epilog=parser_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("db_name", nargs="?", help="CentraXX database name")
    parser.add_argument("--input", help="Path to YAML input file")
    parser.add_argument("--output-dir", help="Directory for output XML files")
    parser.add_argument(
        "--prefix",
        default="org_unit_import",
        help="Filename prefix for generated XML files",
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="Print the demo YAML template and exit",
    )
    return parser


def parse_args() -> argparse.Namespace:
    return create_parser().parse_args()


def main() -> int:
    if len(sys.argv) == 1:
        # Print a friendly guide when no arguments are provided.
        parser = create_parser()
        parser.print_help()
        return 0

    args = parse_args()

    if args.template:
        template_path = (
            Path(__file__).resolve().parent.parent / "templates" / "demo_file.yaml"
        )
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        print(template_path.read_text(encoding="utf-8"))
        return 0

    if not args.db_name or not args.input or not args.output_dir:
        print(
            "Error: Missing required arguments: db_name, --input, and --output-dir are required (-h for help)",
            file=sys.stderr,
        )
        return 1

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    docs = build_xml_documents_from_yaml(input_path, args.db_name)

    output_descriptions = {
        "masterdata": "Organisation unit creation",
        "users": "Assigning users to organisation",
        "studies": "Organisation release for the study",
        "storage_locations": "Storage locations for this organisation",
    }
    generated_files: list[tuple[str, Path]] = []

    for key, xml_root in docs.items():
        output_path = output_dir / f"{args.prefix}_{key}.xml"
        output_path.write_bytes(
            ET.tostring(
                xml_root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
            )
        )
        generated_files.append((key, output_path))
        print(f"XML generated: {output_path}")

    print("\nGenerated XML files and purpose:")
    ordered_keys = ["masterdata", "users", "studies", "storage_locations"]
    for key in ordered_keys:
        match = next((item for item in generated_files if item[0] == key), None)
        if match is None:
            continue
        _, file_path = match
        description = output_descriptions.get(key, key)
        print(f"  - {file_path.name}: {description}")

    print("\nNext steps in Centraxx:")
    print("  1) Go to Administration -> Interfaces -> Import")
    print("  2) Import the generated XML files in the order shown above")
    print(
        "\nNote: There are additional manual steps required in Centraxx after importing the XML files.\n"
    )

    print("\nFurther information:")
    print("  Wiki: http://num-etl:5000/wie%20eine%20organisationseinheit%20erstellen")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
