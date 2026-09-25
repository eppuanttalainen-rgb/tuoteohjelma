import json
from pathlib import Path

from app.parsing import PypdfParser
from scripts.generate_golden_pack import generate_pack


def test_golden_pack_is_deterministic_and_parseable(tmp_path: Path) -> None:
    manifest = generate_pack(tmp_path)

    expected_files = {
        "01_oem_manual_2009.pdf",
        "02_motor_replacement_2021.pdf",
        "03_drive_replacement_2021.pdf",
        "04_safety_modification_2022.pdf",
        "05_plc_inventory.pdf",
        "06_unrelated_motor_datasheet_7_5kw.pdf",
        "07_guard_switch_field_note.pdf",
        "08_duplicate_oem_manual.pdf",
    }
    assert set(manifest["files"]) == expected_files

    stored_manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert stored_manifest == manifest

    original = (tmp_path / "01_oem_manual_2009.pdf").read_bytes()
    duplicate = (tmp_path / "08_duplicate_oem_manual.pdf").read_bytes()
    assert duplicate == original
    assert (
        manifest["files"]["08_duplicate_oem_manual.pdf"]["sha256"]
        == manifest["files"]["01_oem_manual_2009.pdf"]["sha256"]
    )

    assert manifest["expected_current_state"]["motor_power_kw"] == 15
    assert manifest["missing_referenced_documents"] == ["RA-2022-17 risk assessment"]
    assert manifest["unrelated_documents"] == [
        "06_unrelated_motor_datasheet_7_5kw.pdf"
    ]

    parser = PypdfParser()
    for filename in sorted(expected_files):
        pages = parser.parse((tmp_path / filename).read_bytes())
        assert pages
        assert [page.page_number for page in pages] == list(
            range(1, len(pages) + 1)
        )
