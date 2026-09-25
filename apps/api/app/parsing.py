import hashlib
import io
from dataclasses import dataclass

import pypdf
from pypdf import PdfReader


class PdfParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    text_sha256: str


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


class PypdfParser:
    name = "pypdf"
    version = pypdf.__version__

    def parse(self, pdf_bytes: bytes) -> list[ParsedPage]:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
            if len(reader.pages) == 0:
                raise PdfParseError("PDF contains no pages")

            pages: list[ParsedPage] = []
            for page_number, page in enumerate(reader.pages, start=1):
                text = _normalize_text(page.extract_text() or "")
                pages.append(
                    ParsedPage(
                        page_number=page_number,
                        text=text,
                        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    )
                )
            return pages
        except PdfParseError:
            raise
        except Exception as exc:
            raise PdfParseError("PDF parsing failed") from exc


def get_pdf_parser() -> PypdfParser:
    return PypdfParser()
