import argparse
import hashlib
import json
from pathlib import Path

from scripts.synthetic_pdf import make_text_pdf

DOCUMENTS: dict[str, list[str]] = {
    "01_oem_manual_2009.pdf": [
        (
            "NORTHFIELD HANDLING SYSTEMS\n"
            "Machine: CV-204\n"
            "Serial: NHS-CV204-09117\n"
            "Commissioned: 2009\n"
            "Original equipment manual"
        ),
        (
            "DRIVE SYSTEM\n"
            "Motor tag: M1\n"
            "Commissioned: 2009\n"
            "Rated power: 11 kW\n"
            "Supply: 400 V 50 Hz\n"
            "Status: original equipment"
        ),
    ],
    "02_motor_replacement_2021.pdf": [
        (
            "MAINTENANCE MODIFICATION RECORD\n"
            "Machine: CV-204\n"
            "Date: 2021-06-14\n"
            "Motor tag: M1\n"
            "Removed motor: 11 kW\n"
            "Installed motor: 15 kW"
        )
    ],
    "03_drive_replacement_2021.pdf": [
        (
            "VARIABLE SPEED DRIVE CHANGE\n"
            "Machine: CV-204\n"
            "Installed: 2021\n"
            "Drive manufacturer: ABB\n"
            "Drive family: ACS580\n"
            "Associated motor: M1 15 kW"
        )
    ],
    "04_safety_modification_2022.pdf": [
        (
            "SAFETY MODIFICATION RECORD\n"
            "Machine: CV-204\n"
            "Installed: 2022\n"
            "Device: light curtain LC-01\n"
            "Risk assessment reference: RA-2022-17"
        )
    ],
    "05_plc_inventory.pdf": [
        (
            "CONTROL SYSTEM INVENTORY\n"
            "Machine: CV-204\n"
            "PLC platform: Siemens S7-300\n"
            "Cabinet reference: CP-204"
        )
    ],
    "06_unrelated_motor_datasheet_7_5kw.pdf": [
        (
            "GENERIC MOTOR DATASHEET\n"
            "Rated power: 7.5 kW\n"
            "Supply: 400 V 50 Hz\n"
            "No machine tag or CV-204 asset reference"
        )
    ],
    "07_guard_switch_field_note.pdf": [
        (
            "FIELD NOTE\n"
            "Machine: CV-204\n"
            "Guard switch tag: GS-02\n"
            "Model marking partly unreadable: AZM ?\n"
            "Verify exact model on machine"
        )
    ],
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def generate_pack(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict[str, str | int | bool]] = {}

    for filename, pages in DOCUMENTS.items():
        payload = make_text_pdf(pages)
        path = output_dir / filename
        path.write_bytes(payload)
        files[filename] = {
            "sha256": _sha256(payload),
            "page_count": len(pages),
            "duplicate": False,
        }

    original_name = "01_oem_manual_2009.pdf"
    duplicate_name = "08_duplicate_oem_manual.pdf"
    duplicate_payload = (output_dir / original_name).read_bytes()
    (output_dir / duplicate_name).write_bytes(duplicate_payload)
    files[duplicate_name] = {
        "sha256": _sha256(duplicate_payload),
        "page_count": len(DOCUMENTS[original_name]),
        "duplicate": True,
    }

    manifest = {
        "project": "Conveyor Line Retrofit - Test Rig Alpha",
        "machine": {
            "manufacturer": "Northfield Handling Systems",
            "model": "CV-204",
            "serial_number": "NHS-CV204-09117",
            "commissioned": 2009,
        },
        "expected_current_state": {
            "motor_tag": "M1",
            "motor_power_kw": 15,
            "drive_manufacturer": "ABB",
            "drive_family": "ACS580",
            "plc_platform": "Siemens S7-300",
            "light_curtain_tag": "LC-01",
        },
        "expected_history": [
            {"year": 2009, "event": "Original motor 11 kW"},
            {"year": 2021, "event": "Motor replaced with 15 kW unit"},
            {"year": 2021, "event": "Drive replaced with ABB ACS580"},
            {"year": 2022, "event": "Light curtain LC-01 added"},
        ],
        "expected_unknowns": [
            "Exact model of guard switch GS-02 requires field verification",
        ],
        "missing_referenced_documents": [
            "RA-2022-17 risk assessment",
        ],
        "unrelated_documents": [
            "06_unrelated_motor_datasheet_7_5kw.pdf",
        ],
        "duplicate_pairs": [
            [original_name, duplicate_name],
        ],
        "files": files,
    }

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the synthetic CV-204 golden regression document pack."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp/golden_cv204"),
        help="Output directory. Generated files must not be committed to Git.",
    )
    args = parser.parse_args()

    manifest = generate_pack(args.output)
    print(
        f"Generated {len(manifest['files'])} synthetic PDFs and manifest.json "
        f"in {args.output}"
    )


if __name__ == "__main__":
    main()
