from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD = ROOT / 'books' / 'print-edition' / 'book-print-ready-full.md'
OUTPUT_PDF = ROOT / 'books' / 'print-edition' / 'EPL_Complete_Book_Abneesh_Singh_COMPLETE.pdf'
LOGO = ROOT / 'books' / 'assets' / 'epl_logo_minimal.png'


PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 0.75 * inch
RIGHT_MARGIN = 0.75 * inch
TOP_MARGIN = 0.75 * inch
BOTTOM_MARGIN = 0.75 * inch
FONT_NAME = 'Courier'
FONT_SIZE = 9
LEADING = 11
LINES_PER_PAGE = 32


def _estimate_chars_per_line() -> int:
    usable_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    # Courier is fixed width; this approximation works well for print layout.
    char_width = FONT_SIZE * 0.60
    return max(60, int(usable_width / char_width))


def _normalized_lines(text: str) -> list[str]:
    lines: list[str] = []
    width = _estimate_chars_per_line()

    for raw in text.splitlines():
        line = raw.replace('\t', '    ')

        # Respect explicit page break markers used in the manuscript.
        if line.strip() == '\\newpage':
            lines.append('\f')
            continue

        # Keep blank lines.
        if not line.strip():
            lines.append('')
            continue

        # Keep one input line as one output line to preserve source pagination.
        if len(line) > width:
            lines.append(line[:width])
        else:
            lines.append(line)

    return lines


def _draw_title_page(pdf: canvas.Canvas) -> None:
    pdf.setTitle('EPL: The Complete Book')
    pdf.setAuthor('Abneesh Singh')

    y = PAGE_HEIGHT - 1.5 * inch

    if LOGO.exists():
        try:
            logo_w = 2.4 * inch
            logo_h = 2.4 * inch
            x = (PAGE_WIDTH - logo_w) / 2
            pdf.drawImage(
                str(LOGO),
                x,
                y - logo_h,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask='auto',
            )
            y -= logo_h + 0.4 * inch
        except Exception:
            pass

    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawCentredString(PAGE_WIDTH / 2, y, 'EPL: The Complete Book')
    y -= 0.35 * inch

    pdf.setFont('Helvetica', 14)
    pdf.drawCentredString(PAGE_WIDTH / 2, y, 'Author: Abneesh Singh')
    y -= 0.25 * inch

    pdf.setFont('Helvetica', 11)
    pdf.drawCentredString(PAGE_WIDTH / 2, y, 'Complete Print Edition')

    pdf.showPage()


def build_pdf() -> tuple[int, int]:
    if not SOURCE_MD.exists():
        raise FileNotFoundError(f'Source manuscript not found: {SOURCE_MD}')

    text = SOURCE_MD.read_text(encoding='utf-8', errors='replace')
    lines = _normalized_lines(text)

    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT_PDF), pagesize=A4)

    pdf.setFont(FONT_NAME, FONT_SIZE)
    cursor_y = PAGE_HEIGHT - TOP_MARGIN
    lines_on_page = 0
    pages = 1

    for line in lines:
        if line == '\f':
            pdf.showPage()
            pages += 1
            pdf.setFont(FONT_NAME, FONT_SIZE)
            cursor_y = PAGE_HEIGHT - TOP_MARGIN
            lines_on_page = 0
            continue

        if lines_on_page >= LINES_PER_PAGE or cursor_y <= BOTTOM_MARGIN:
            pdf.showPage()
            pages += 1
            pdf.setFont(FONT_NAME, FONT_SIZE)
            cursor_y = PAGE_HEIGHT - TOP_MARGIN
            lines_on_page = 0

        pdf.drawString(LEFT_MARGIN, cursor_y, line)
        cursor_y -= LEADING
        lines_on_page += 1

    pdf.save()
    return len(lines), pages


if __name__ == '__main__':
    total_lines, total_pages = build_pdf()
    print(f'Generated: {OUTPUT_PDF}')
    print(f'Rendered lines: {total_lines}')
    print(f'PDF pages: {total_pages}')
