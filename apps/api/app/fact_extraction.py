import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

DATE_PATTERN = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})$", re.MULTILINE)
MACHINE_PATTERN = re.compile(r"^Machine:\s*(.+)$", re.MULTILINE)
SERIAL_PATTERN = re.compile(r"^Serial:\s*(.+)$", re.MULTILINE)
MOTOR_TAG_PATTERN = re.compile(r"^Motor tag:\s*([A-Za-z0-9_-]+)$", re.MULTILINE)
POWER_PATTERN = re.compile(
    r"^(Rated power|Removed motor|Installed motor):\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*kW$",
    re.MULTILINE,
)
DRIVE_MANUFACTURER_PATTERN = re.compile(
    r"^Drive manufacturer:\s*(.+)$",
    re.MULTILINE,
)
DRIVE_FAMILY_PATTERN = re.compile(r"^Drive family:\s*(.+)$", re.MULTILINE)
PLC_PATTERN = re.compile(r"^PLC platform:\s*(.+)$", re.MULTILINE)
LIGHT_CURTAIN_PATTERN = re.compile(
    r"^Device:\s*light curtain\s+([A-Za-z0-9_-]+)$",
    re.MULTILINE | re.IGNORECASE,
)
GUARD_TAG_PATTERN = re.compile(
    r"^Guard switch tag:\s*([A-Za-z0-9_-]+)$",
    re.MULTILINE,
)
GUARD_MODEL_PATTERN = re.compile(
    r"^Model marking partly unreadable:\s*(.+)$",
    re.MULTILINE,
)
MANUFACTURER_PATTERN = re.compile(
    r"^([A-Z][A-Z0-9 &.-]+ SYSTEMS)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ExtractedFact:
    fact_key: str
    raw_value: str
    normalized_value: Any
    unit: str | None
    confidence: float
    source_excerpt: str
    effective_date: date | None = None


class DeterministicFactExtractor:
    name = "deterministic_rules"
    version = "golden-v1"

    def extract(self, text: str) -> list[ExtractedFact]:
        facts: list[ExtractedFact] = []
        effective_date = self._effective_date(text)

        self._append_matches(
            facts,
            text,
            MANUFACTURER_PATTERN,
            "machine.manufacturer",
            confidence=0.95,
        )
        self._append_matches(
            facts,
            text,
            MACHINE_PATTERN,
            "machine.model",
            confidence=0.99,
        )
        self._append_matches(
            facts,
            text,
            SERIAL_PATTERN,
            "machine.serial_number",
            confidence=0.99,
        )
        self._append_matches(
            facts,
            text,
            MOTOR_TAG_PATTERN,
            "motor.tag",
            confidence=0.99,
        )
        self._append_power_matches(facts, text, effective_date)
        self._append_matches(
            facts,
            text,
            DRIVE_MANUFACTURER_PATTERN,
            "drive.manufacturer",
            confidence=0.99,
            effective_date=effective_date,
        )
        self._append_matches(
            facts,
            text,
            DRIVE_FAMILY_PATTERN,
            "drive.family",
            confidence=0.99,
            effective_date=effective_date,
        )
        self._append_matches(
            facts,
            text,
            PLC_PATTERN,
            "plc.platform",
            confidence=0.99,
        )
        self._append_matches(
            facts,
            text,
            LIGHT_CURTAIN_PATTERN,
            "safety.light_curtain.tag",
            confidence=0.99,
            effective_date=effective_date,
        )
        self._append_matches(
            facts,
            text,
            GUARD_TAG_PATTERN,
            "safety.guard_switch.tag",
            confidence=0.99,
        )
        self._append_matches(
            facts,
            text,
            GUARD_MODEL_PATTERN,
            "safety.guard_switch.model",
            confidence=0.45,
        )
        return facts

    @staticmethod
    def _effective_date(text: str) -> date | None:
        match = DATE_PATTERN.search(text)
        if match is None:
            return None
        return date.fromisoformat(match.group(1))

    @staticmethod
    def _source_line(text: str, match: re.Match[str]) -> str:
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        return text[line_start:line_end].strip()

    def _append_matches(
        self,
        facts: list[ExtractedFact],
        text: str,
        pattern: re.Pattern[str],
        fact_key: str,
        confidence: float,
        effective_date: date | None = None,
    ) -> None:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            facts.append(
                ExtractedFact(
                    fact_key=fact_key,
                    raw_value=value,
                    normalized_value=value,
                    unit=None,
                    confidence=confidence,
                    source_excerpt=self._source_line(text, match),
                    effective_date=effective_date,
                )
            )

    def _append_power_matches(
        self,
        facts: list[ExtractedFact],
        text: str,
        effective_date: date | None,
    ) -> None:
        for match in POWER_PATTERN.finditer(text):
            raw_number = match.group(2)
            numeric_value = float(raw_number)
            normalized_value: int | float = (
                int(numeric_value) if numeric_value.is_integer() else numeric_value
            )
            facts.append(
                ExtractedFact(
                    fact_key="motor.power_kw",
                    raw_value=raw_number,
                    normalized_value=normalized_value,
                    unit="kW",
                    confidence=0.99,
                    source_excerpt=self._source_line(text, match),
                    effective_date=effective_date,
                )
            )


def candidate_fingerprint(
    document_page_id: uuid.UUID,
    fact: ExtractedFact,
    extraction_method: str,
    extraction_version: str,
) -> str:
    payload = json.dumps(
        {
            "document_page_id": str(document_page_id),
            "fact_key": fact.fact_key,
            "raw_value": fact.raw_value,
            "normalized_value": fact.normalized_value,
            "unit": fact.unit,
            "source_excerpt": fact.source_excerpt,
            "effective_date": (
                fact.effective_date.isoformat() if fact.effective_date else None
            ),
            "extraction_method": extraction_method,
            "extraction_version": extraction_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_fact_extractor() -> DeterministicFactExtractor:
    return DeterministicFactExtractor()
