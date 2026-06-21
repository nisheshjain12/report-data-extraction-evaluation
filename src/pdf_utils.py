"""
Text extraction from 10-K PDFs.

`read_text` returns the document as flattened plain text. Flattening discards
table structure, which is the main source of extraction error (wrong column,
wrong line item, units).
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


if __name__ == "__main__":
    # Manual check: total text length and a sample around "research and development".
    text = read_text("AAPL_2025")
    print(f"Characters extracted: {len(text):,}")

    i = text.lower().find("research and development")
    print("\n--- raw text around 'research and development' ---")
    print(text[i - 150 : i + 250])
