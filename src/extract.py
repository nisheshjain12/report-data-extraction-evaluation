"""
The extractor. Three versions:

  v1 -- Baseline: minimal prompt, no unit or definition guidance.
  v2 -- Refined prompt: specifies the output unit (millions) and precise field definitions.
  v3 -- Structured output: the response is constrained to a Pydantic schema via Gemini's
        `response_schema`, so the JSON is schema-guaranteed (no manual parsing). Each value
        also carries traceability (unit, fiscal_year, source_page); the text is page-marked
        so the model can cite the source page.

Run:
  python src/extract.py            -> v1, all 10
  python src/extract.py v2         -> v2, all 10
  python src/extract.py v3         -> v3, all 10
  python src/extract.py v3 AAPL_2025
"""

import json
import sys
import time
from typing import Optional

import pandas as pd
from pydantic import BaseModel

import config
import llm
import pdf_utils


# --- v3 structured-output schema ----------------------------------------------
class FieldValue(BaseModel):
    value: Optional[float] = None       # the number, in millions of USD
    unit: Optional[str] = None          # the unit shown in the statement, e.g. "millions"
    fiscal_year: Optional[int] = None   # the fiscal year this value is for
    source_page: Optional[int] = None   # PDF page (from the markers) where it was found


class Extraction(BaseModel):
    rd_expense: FieldValue
    capex: FieldValue
    long_term_debt: FieldValue


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

# --- v3: structured output (schema-enforced JSON) + traceability ---------------
PROMPT_V3 = """You are extracting figures from a company's 10-K annual report.
The text below is marked with "===== PDF PAGE n =====" lines.

For each of the three fields report:
- value: the number in MILLIONS of US dollars, exactly as printed (do NOT convert to full dollars)
- unit: the unit the statement uses (e.g. "millions")
- fiscal_year: the fiscal year this value is for (use the most recent year shown)
- source_page: the PDF page number (from the markers) where you found the value

Field definitions:
- rd_expense: the "research and development" expense on the income statement.
- capex: the "purchases of property and equipment" / "additions to property, plant and
  equipment" line in the cash-flow statement, as a POSITIVE number. Use the GROSS purchases
  line -- NOT a figure described as "net of proceeds", and NOT one that includes finance leases.
- long_term_debt: long-term debt EXCLUDING the current portion, from the balance sheet
  (the non-current long-term-debt or notes-payable line).

If a value genuinely does not exist, set its value to null.

10-K TEXT:
{text}
"""

PROMPTS = {"v1": PROMPT_V1, "v2": PROMPT_V2}   # text prompts (manual JSON)
VERSIONS = ["v1", "v2", "v3"]


def _parse_json(reply: str) -> dict:
    """Pull the JSON object out of a v1/v2 reply (handles ``` fences)."""
    s = reply.strip()
    start, end = s.find("{"), s.rfind("}")
    return json.loads(s[start : end + 1])


def extract_company(stem: str, version: str = "v1") -> dict:
    """Run extraction on one PDF. Returns {field: {value, unit, fiscal_year, source_page}}."""
    if version == "v3":
        text = pdf_utils.read_text_with_pages(stem)
        result = llm.ask_structured(PROMPT_V3.format(text=text), Extraction)
        if result is None:
            return {f: {} for f in config.FIELDS}
        return {f: getattr(result, f).model_dump() for f in config.FIELDS}
    # v1 / v2: plain "return JSON" + manual parse
    text = pdf_utils.read_text(stem)
    vals = _parse_json(llm.ask(PROMPTS[version].format(text=text)))
    return {f: {"value": vals.get(f)} for f in config.FIELDS}


def run_all(version: str = "v1") -> None:
    config.RESULTS_DIR.mkdir(exist_ok=True)
    rows = []
    for stem, fy in config.COMPANIES.items():
        try:
            vals = extract_company(stem, version)
        except Exception as e:
            vals = {f: {} for f in config.FIELDS}
            print(f"{stem}: ERROR {e}")
        print(f"{stem}: { {f: vals[f].get('value') for f in config.FIELDS} }")
        for field in config.FIELDS:
            d = vals.get(field, {})
            rows.append({
                "version": version,
                "company": stem.split("_")[0],
                "fiscal_year": fy,
                "field": field,
                "predicted": d.get("value"),
                "pred_unit": d.get("unit"),          # v3 traceability (None for v1/v2)
                "pred_fiscal_year": d.get("fiscal_year"),
                "source_page": d.get("source_page"),
            })
        time.sleep(5)  # stay under the free-tier per-minute rate limit
    out = config.RESULTS_DIR / f"extraction_{version}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nWrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    # args (any order): a version key ("v1"/"v2"/"v3") and/or a company stem.
    version, stem = "v1", None
    for arg in sys.argv[1:]:
        if arg in VERSIONS:
            version = arg
        else:
            stem = arg
    if stem:
        print(stem, "->", extract_company(stem, version))
    else:
        run_all(version)
