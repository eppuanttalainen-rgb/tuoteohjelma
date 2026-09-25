def _escape_pdf_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _content_stream(text: str) -> bytes:
    lines = text.splitlines() or [""]
    commands = [
        "BT",
        "/F1 12 Tf",
        "14 TL",
        "72 720 Td",
    ]

    for index, line in enumerate(lines):
        if index > 0:
            commands.append("T*")
        commands.append(f"({_escape_pdf_text(line)}) Tj")

    commands.append("ET")
    return ("\n".join(commands) + "\n").encode("ascii")


def make_text_pdf(pages: list[str]) -> bytes:
    if not pages:
        raise ValueError("At least one page is required")

    page_object_ids = [4 + (index * 2) for index in range(len(pages))]
    kids = " ".join(f"{object_id} 0 R" for object_id in page_object_ids)

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    for index, text in enumerate(pages):
        page_id = page_object_ids[index]
        content_id = page_id + 1
        stream = _content_stream(text)

        page_object = (
            "<< /Type /Page "
            "/Parent 2 0 R "
            "/MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")
        content_object = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )

        objects.extend([page_object, content_object])

    output = bytearray(b"%PDF-1.4\n%synthetic\n")
    offsets = [0]

    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)
