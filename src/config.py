"""
Central configuration for the 10-K extraction pipeline.

All tunable settings live here so they can be changed in one place:
  - MODEL      the Gemini model used for extraction
  - FIELDS     the three fields to extract, with their definitions
  - COMPANIES  the reports to process and their fiscal years
  - TOLERANCE  the relative error within which a prediction counts as correct
"""

from pathlib import Path

# --- Paths (auto-resolved from this file's location) ---------------------------
ROOT = Path(__file__).resolve().parent.parent      # the project root folder
PDF_DIR = ROOT / "data" / "pdfs"                   # where the 10 PDFs live
GROUND_TRUTH = ROOT / "data" / "ground_truth.csv"  # our hand-checked answer key
RESULTS_DIR = ROOT / "results"                     # extraction outputs go here

# --- The model (free Gemini tier) ----------------------------------------------
MODEL = "gemini-2.5-flash-lite"  # used for v2 (v1's kept results are from gemini-2.5-flash)

# --- The three fields to extract, with their definitions -----------------------
# The definitions are sent to the model in v2 to steer extraction.
FIELDS = {
    "rd_expense":
        "Research & development expense for the fiscal year, from the income statement.",
    "capex":
        "Capital expenditures: cash paid to purchase property, plant & equipment "
        "(from the cash-flow statement), reported as a positive number.",
    "long_term_debt":
        "Long-term debt EXCLUDING the current portion, from the balance sheet.",
}

# --- The 10 companies: PDF filename stem -> fiscal year ------------------------
COMPANIES = {
    "AAPL_2025": 2025, "AMZN_2025": 2025, "CSCO_2025": 2025, "GOOGL_2025": 2025,
    "INTC_2025": 2025, "META_2025": 2025, "MSFT_2025": 2025, "NVDA_2026": 2026,
    "ORCL_2025": 2025, "TSLA_2025": 2025,
}

# --- Evaluation ----------------------------------------------------------------
# A predicted number counts as "correct" if it is within this relative error of
# the ground-truth value (0.005 = 0.5%, which absorbs rounding differences).
TOLERANCE = 0.005
