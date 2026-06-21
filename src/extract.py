"""
The extractor. Two versions:

  v1 -- Baseline: minimal prompt, no unit or definition guidance.
  v2 -- Refined prompt: specifies the output unit (millions) and precise field definitions.

Run:
  python src/extract.py                  -> v1, all 10
  python src/extract.py v2               -> v2, all 10
  python src/extract.py v2 AAPL_2025     -> v2, one company
"""

import json
import sys
import time

import pandas as pd

import config
import llm
import pdf_utils

# --- v1: baseline prompt ------------------------------------------------------
PROMPT_V1 = """You are reading a company's 10-K annual report (text below).
Extract these three figures and reply with ONLY a JSON object, nothing else:

{{"rd_expense": <number>, "capex": <number>, "long_term_debt": <number>}}

- rd_expense: research and development expense
- capex: capital expenditures (cash spent on property, plant and equipment)
- long_term_debt: long-term debt

Use plain numbers (no commas, no $, no words). Use null if a value is not found.

10-K TEXT:
{text}
"""

# --- v2: explicit unit + field definitions ------------------------------------
PROMPT_V2 = """You are extracting figures from a company's 10-K annual report (text below).
Reply with ONLY this JSON object, nothing else:

{{"rd_expense": <number>, "capex": <number>, "long_term_debt": <number>}}

Rules:
- Report every value in MILLIONS of US dollars, exactly as printed in the
  financial statements. Do NOT convert to full dollars.
- Use the MOST RECENT fiscal year shown.
- rd_expense: the "research and development" expense on the income statement.
- capex: the "purchases of property and equipment" / "additions to property,
  plant and equipment" line in the cash-flow statement's investing section, as a
  POSITIVE number. Use the GROSS purchases line -- NOT a figure described as
  "net of proceeds", and NOT one that includes finance leases.
- long_term_debt: the long-term debt balance EXCLUDING the current portion, from
  the balance sheet (the non-current long-term debt or notes-payable line).
- Use null only if a value genuinely does not exist.

10-K TEXT:
{text}
"""

PROMPTS = {"v1": PROMPT_V1, "v2": PROMPT_V2}


def _parse_json(reply: str) -> dict:
    """Pull the JSON object out of the model's reply (handles ``` fences)."""
    s = reply.strip()
    start, end = s.find("{"), s.rfind("}")
    return json.loads(s[start : end + 1])


def extract_company(stem: str, version: str = "v1") -> dict:
    """Run extraction on one PDF with the chosen prompt version. Returns {field: number}."""
    text = pdf_utils.read_text(stem)
    return _parse_json(llm.ask(PROMPTS[version].format(text=text)))


def run_all(version: str = "v1") -> None:
    config.RESULTS_DIR.mkdir(exist_ok=True)
    rows = []
    for stem, fy in config.COMPANIES.items():
        try:
            vals = extract_company(stem, version)
        except Exception as e:
            vals = {}
            print(f"{stem}: ERROR {e}")
        print(f"{stem}: {vals}")
        for field in config.FIELDS:
            rows.append({
                "version": version,
                "company": stem.split("_")[0],
                "fiscal_year": fy,
                "field": field,
                "predicted": vals.get(field),
            })
        time.sleep(5)  # stay under the free-tier per-minute rate limit
    out = config.RESULTS_DIR / f"extraction_{version}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nWrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    # args (any order): a version key ("v1"/"v2") and/or a company stem.
    version, stem = "v1", None
    for arg in sys.argv[1:]:
        if arg in PROMPTS:
            version = arg
        else:
            stem = arg
    if stem:
        print(stem, "->", extract_company(stem, version))
    else:
        run_all(version)
