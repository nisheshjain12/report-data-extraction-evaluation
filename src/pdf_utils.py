"""
Text extraction from 10-K PDFs.

`read_text` returns the document as flattened plain text (used by v1 and v2).
`read_text_with_pages` adds per-page markers so the model can cite a source page
(used by v3). Flattening discards table structure, which is the main source of
extraction error for the text-based versions (wrong column, wrong line item, units).
"""

import pdfplumber

import config


def read_text(stem: str) -> str:
    """Return all text from data/pdfs/<stem>.pdf as a single string."""
    path = config.PDF_DIR / f"{stem}.pdf"
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)

def read_text_with_pages(stem: str) -> str:
    """Like read_text, but prefix each page with a marker so the model can cite the PDF page.

    Used by v3 (structured output) so the model can report a `source_page` for traceability.
    """
    path = config.PDF_DIR / f"{stem}.pdf"
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append(f"===== PDF PAGE {i} =====\n" + (page.extract_text() or ""))
    return "\n".join(pages)


if __name__ == "__main__":
    # Manual check: total text length and a sample around "research and development".
    text = read_text("AAPL_2025")
    print(f"Characters extracted: {len(text):,}")

    i = text.lower().find("research and development")
    print("\n--- raw text around 'research and development' ---")
    print(text[i - 150 : i + 250])
