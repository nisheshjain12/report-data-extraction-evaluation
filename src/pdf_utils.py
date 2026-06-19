"""
Turn a 10-K PDF into plain text.

The v1 (naive) extractor feeds this flat text straight to the model. Notice how
tables collapse into runs of numbers with the labels detached — THAT mess is
why v1 will make mistakes (wrong column, wrong line item, units). It's
intentional: it gives us real errors to analyze and then fix in v2.
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
    # Demo on Apple: show how much text we get and how messy a table looks.
    text = read_text("AAPL_2025")
    print(f"Characters extracted: {len(text):,}")

    i = text.lower().find("research and development")
    print("\n--- raw text around 'research and development' ---")
    print(text[i - 150 : i + 250])
