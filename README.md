# 10-K Report Data Extraction & Evaluation

A pipeline that extracts numerical financial data from public companies' 10-K annual
reports (PDF) and measures the accuracy of those extractions against a hand-verified
ground truth. Extraction is performed with a large language model (Google Gemini); the
project demonstrates an error-analysis-driven iteration from a naive baseline to a
refined, schema-constrained extractor.

## What it does

- Reads 10 companies' 10-K reports (PDF) and extracts **three numerical fields** from
  each: **R&D expense**, **capital expenditures**, and **long-term debt**.
- Scores the extractions against a **hand-labelled, page-cited ground truth** (30 values)
  using tolerance-based accuracy and an error-category breakdown.
- Iterates on the extractor so accuracy improves as observed errors are addressed.
- Provides a **Streamlit dashboard** that visualizes the extracted values and the
  accuracy / error metrics.

### Companies & fields

| | |
|---|---|
| Companies (10) | Apple, Microsoft, Alphabet, Amazon, Meta, NVIDIA, Intel, Cisco, Oracle, Tesla |
| Fields (3) | `rd_expense` (income statement), `capex` (cash-flow statement), `long_term_debt` (balance sheet) |

### Results

| Version | Approach | Accuracy |
|---|---|---|
| v1 | Naive prompt over flattened PDF text | **80%** (24/30) |
| v2 | Prompt with explicit units + field definitions | **93.3%** (28/30) |
| v3 | Schema-constrained JSON output + per-value traceability | Implemented (full run subject to daily quota) |

The v1 → v2 improvement was driven by error analysis: v1's errors were unit
inconsistencies and field-definition ambiguity, both addressed in the v2 prompt. v3 uses
the model's structured-output mode so the JSON response is schema-guaranteed (no manual
parsing) and each value carries traceability — `unit`, `fiscal_year`, and `source_page`.

## How it works

```
PDF ──pdfplumber──► text ──► Gemini (prompt) ──► JSON ──► results CSV ──► evaluate ──► metrics
```

| File | Responsibility |
|---|---|
| `src/config.py` | Central configuration: model, fields, companies, tolerance, paths |
| `src/pdf_utils.py` | Extract text from a PDF |
| `src/llm.py` | The single Gemini client (text and structured-output calls) |
| `src/extract.py` | The three extractor versions (v1 / v2 / v3) |
| `src/evaluate.py` | Score predictions vs ground truth; categorize errors |
| `dashboard/app.py` | Streamlit dashboard over the result CSVs |

## Setup

Requires **Python 3.11+**.

1. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
2. Get a free Google Gemini API key: https://aistudio.google.com/apikey
3. Create a `.env` file in the project root (copy from `.env.example`):
   ```
   GEMINI_API_KEY=your-key-here
   ```

The 10 PDFs (`data/pdfs/`) and the ground truth (`data/ground_truth.csv`) are included,
so no data download is required.

## Running

```bash
# Extraction — writes results/extraction_<version>.csv
python src/extract.py v1                 # naive baseline
python src/extract.py v2                 # refined prompt
python src/extract.py v3                 # structured output
python src/extract.py v3 AAPL_2025       # a single company

# Evaluation — writes results/metrics.csv and results/scored.csv
python src/evaluate.py

# Dashboard — opens at http://localhost:8501
streamlit run dashboard/app.py
```

### Free-tier rate limits

The Gemini free tier allows roughly **20 requests per day, per model**. A full extraction
run is 10 requests, so running v1 + v2 + v3 in one day can exceed the cap. On
`429 RESOURCE_EXHAUSTED`, wait for the daily reset or change `MODEL` in `src/config.py`
to another model (each model has its own daily quota).

## Configuration

All tunable settings live in `src/config.py`: the model ID, the three field definitions,
the company list, and the accuracy tolerance.

## Repository layout

```
report-data-extraction-evaluation/
├── README.md
├── architecture.md            # design, error taxonomy, as-built notes
├── requirements.txt
├── .env.example               # template; real .env is gitignored
├── data/
│   ├── pdfs/                   # 10 10-K PDFs
│   └── ground_truth.csv        # hand-labelled answer key
├── src/
│   ├── config.py
│   ├── llm.py
│   ├── pdf_utils.py
│   ├── extract.py
│   └── evaluate.py
├── results/                    # extraction outputs + metrics
└── dashboard/
    └── app.py
```

## Notes & limitations

- During development a free-tier quota limit required switching models mid-project: v1's
  results are from `gemini-2.5-flash` and v2 from `gemini-2.5-flash-lite`. The prompt is
  the change that drives the v1 → v2 improvement; see `architecture.md` § 15 for details.
- Two extraction errors remain in v2 (Amazon capital expenditures, Tesla long-term debt);
  these are documented as candidates for further refinement.
- See `architecture.md` for the full design, error taxonomy, and as-built notes.
```
