"""确定性生成第 04 讲的文字型 PDF Fixture。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "fixtures" / "pdf" / "source"
OUTPUT_DIR = ROOT / "fixtures" / "pdf"


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -20 Td")
        commands.append("(%s) Tj" % _escape_pdf_text(line))
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(b"%d 0 obj\n" % number)
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(b"xref\n0 %d\n" % (len(objects) + 1))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(b"%010d 00000 n \n" % offset)
    output.extend(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref_offset)
    )
    return bytes(output)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for variant in ("clean", "injected"):
        lines = SOURCE_DIR.joinpath(variant + ".txt").read_text(
            encoding="utf-8"
        ).splitlines()
        OUTPUT_DIR.joinpath(variant + ".pdf").write_bytes(render_pdf(lines))
    print("Lesson 04 PDF fixtures generated.")


if __name__ == "__main__":
    main()
