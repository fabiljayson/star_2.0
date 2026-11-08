from __future__ import annotations

import csv
import html
import io

from .models import ReportFormat

# Characters that spreadsheet apps treat as the start of a formula.
_UNSAFE_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    """Neutralize CSV/XLSX formula injection (OWASP: prefix with an apostrophe)."""
    text = "" if value is None else str(value)
    if text.startswith(_UNSAFE_PREFIXES):
        return "'" + text
    return text


def render_csv(title: str, headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([csv_safe(cell) for cell in headers])
    for row in rows:
        writer.writerow([csv_safe(cell) for cell in row])
    # utf-8-sig keeps Excel happy with accented characters.
    return ("# " + title + "\n" + buffer.getvalue()).encode("utf-8-sig")


_PDF_STYLE = """
@page { size: A4 landscape; margin: 1.5cm; @bottom-right { content: counter(page) " / " counter(pages); } }
body { font-family: sans-serif; font-size: 9pt; color: #111; }
h1 { font-size: 14pt; margin: 0 0 2pt; }
.meta { color: #555; font-size: 8pt; margin: 0 0 10pt; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 0.5pt solid #999; padding: 3pt 5pt; text-align: left; }
th { background: #f2f2f2; font-weight: bold; }
tr:nth-child(even) td { background: #fafafa; }
.empty { color: #777; font-style: italic; margin-top: 8pt; }
"""


def render_pdf(title: str, subtitle: str, headers: list[str], rows: list[list]) -> bytes:
    # Imported lazily: weasyprint eagerly dlopens Pango/HarfBuzz at import time,
    # which would crash the whole app at boot on hosts without those system libs.
    import weasyprint

    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    if rows:
        body = "".join(
            "<tr>"
            + "".join(
                f"<td>{html.escape('' if cell is None else str(cell))}</td>"
                for cell in row
            )
            + "</tr>"
            for row in rows
        )
        table = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    else:
        table = (
            f"<table><thead><tr>{head}</tr></thead></table>"
            '<p class="empty">No records matched the selected filters.</p>'
        )
    document = (
        f"<html><head><meta charset='utf-8'><style>{_PDF_STYLE}</style></head>"
        f"<body><h1>{safe_title}</h1><p class='meta'>{safe_subtitle}</p>{table}"
        "</body></html>"
    )
    return weasyprint.HTML(string=document).write_pdf()


def render_document(
    fmt: str, title: str, subtitle: str, headers: list[str], rows: list[list]
) -> tuple[bytes, str]:
    if fmt == ReportFormat.PDF:
        return render_pdf(title, subtitle, headers, rows), "application/pdf"
    return render_csv(title, headers, rows), "text/csv; charset=utf-8"
