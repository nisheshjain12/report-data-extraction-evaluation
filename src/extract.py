"""
v1 -- the NAIVE extractor (the deliberately-imperfect first pass).

Naive on purpose:
  * feeds the whole flattened pdfplumber text to the model
  * a minimal prompt ("find these 3 numbers, return JSON")
  * NO units guidance, NO fiscal-year pin, NO page hint, NO normalization
Those gaps create the errors we analyze in Phase 4 and fix in v2.

Run one company:   python src/extract.py AAPL_2025
Run all 10:        python src/extract.py
"""

import json
import sys
import time

import pandas as pd

import config
import llm
import pdf_utils

# Bare-bones prompt: no hints about units, year, or where in the report to look.
PROMPT = """You are reading a company's 10-K annual report (text below).
Extract these three figures and reply with ONLY a JSON object, nothing else:

{{"rd_expense": <number>, "capex": <number>, "long_term_debt": <number>}}

- rd_expense: research and development expense
- capex: capital expenditures (cash spent on property, plant and equipment)
- long_term_debt: long-term debt

Use plain numbers (no commas, no $, no words). Use null if a value is not found.

10-K TEXT:
{text}
"""


def _parse_json(reply: str) -> dict:
    """Pull the JSON object out of the model's reply (handles ``` fences)."""
    s = reply.strip()
    start, end = s.find("{"), s.rfind("}")
    return json.loads(s[start : end + 1])


def extract_company(stem: str) -> dict:
    """Run v1 extraction on one PDF -> {field: number}."""
    text = pdf_utils.read_text(stem)
    reply = llm.ask(PROMPT.format(text=text))
    return _parse_json(reply)


def run_all() -> None:
    config.RESULTS_DIR.mkdir(exist_ok=True)
    rows = []
    for stem, fy in config.COMPANIES.items():
        try:
            vals = extract_company(stem)
        except Exception as e:
            vals = {}
            print(f"{stem}: ERROR {e}")
        print(f"{stem}: {vals}")
        for field in config.FIELDS:
            rows.append({
                "version": "v1",
                "company": stem.split("_")[0],
                "fiscal_year": fy,
                "field": field,
                "predicted": vals.get(field),
            })
        time.sleep(6)  # stay under the free-tier per-minute rate limit
    out = config.RESULTS_DIR / "extraction_v1.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nWrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    if len(sys.argv) > 1:                  # one company: python src/extract.py AAPL_2025
        stem = sys.argv[1]
        print(stem, "->", extract_company(stem))
    else:                                  # all 10
        run_all()
