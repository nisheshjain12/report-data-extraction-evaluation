# 10-K Data Extraction & Evaluation — Architecture & Plan

> Planning document. No code yet. The goal is a **simple, completable** system that meets every
> stated requirement — and, crucially, produces a *first pass with real
> errors* so there's a genuine error-analysis and iteration story to tell.

---

## 1. What the assessment asks for (checklist)

| # | Requirement | How we meet it |
|---|---|---|
| 1 | ≥ 10 different companies' 10-Ks, **all PDF** | 10 large-cap PDFs in `data/pdfs/` |
| 2 | Extract **3 distinct numerical fields**, "reasonably challenging" | R&D expense, Capital expenditures, Total long-term debt (§3) |
| 3 | **Ground truth** dataset | Hand-labelled `data/ground_truth.csv` (§5) |
| 4 | Evaluate with **appropriate metrics** | Tolerance-accuracy + MAPE + error taxonomy (§7) |
| 5 | **First pass not perfect** | Naive text-only baseline → predictable, analyzable errors (§6) |
| 6 | **≥ 1 refinement iteration** | v2 pipeline targeting the dominant error class (§6, §8) |
| 7 | **Error analysis methodology** | Categorized error taxonomy driving v2 (§7) |
| 8 | **Bonus:** dashboard | Streamlit app (§9) |

---

## 2. Design principles

- **Keep it boring.** Plain Python scripts + CSVs. No database, no queue, no web backend.
- **Free model, fixed across iterations.** We use a free LLM (Google **Gemini Flash** free tier — §6).
  Improvements must come from *pipeline/prompt* changes, not from swapping models — that's what makes
  the iteration story credible, and a free model keeps v1 honestly imperfect. The LLM call is isolated
  in one module (`src/llm.py`) so the provider can be swapped (Ollama, Claude, …) without touching the
  rest of the pipeline.
- **The PDF is the source of truth.** We parse the actual PDF (not pre-cleaned data), because the
  messiness of PDF tables is exactly what creates the errors worth analyzing.
- **Everything is reproducible.** A single command regenerates each iteration's results and metrics.

---

## 3. The three fields (the most important decision)

Chosen to be **non-trivial but consistent**, and to live in **three different financial statements** so
extraction has to range across the document:

| Field | Lives in | Why it's challenging (= where v1 will fail) |
|---|---|---|
| **R&D expense** | Income statement / notes | Label varies ("Research and development", "Technology and content", "Product development"); sometimes only in a note, not the face statement. |
| **Capital expenditures** | Cash flow statement | Label varies wildly ("Purchases of property and equipment", "Additions to PP&E", "Capital expenditures"); reported as a **negative** number; easy to confuse with acquisitions/intangibles. |
| **Total long-term debt** | Balance sheet | "Long-term debt" vs "Long-term debt, net of current portion"; current portion sits on a different line; gross vs net. |

**Built-in difficulty shared by all three:**
- **Units/scale** — statements say "(in thousands)" or "(in millions)". A naive read returns `1,234`
  when the truth is `1,234,000,000`. This is the richest error source.
- **Fiscal-year column** — statements show 2–3 years side by side. v1 will sometimes grab the prior year.

> **Company selection guarantees field presence:** pick 10 large-caps that all report R&D + capex +
> debt — e.g. Apple, Microsoft, Alphabet, Amazon, Meta, NVIDIA, Intel, Cisco, Oracle, Tesla. This is a
> deliberate simplification so we never have a "field doesn't exist" edge case derailing the metrics.
>
> **If the first pass turns out too easy**, swap *Total long-term debt* for **"Revenue from largest
> geographic region"** (US/Americas) — a footnote-only value that's much harder to locate. Hold this in
> reserve; don't start here.

---

## 4. Data acquisition

10-Ks on SEC EDGAR are HTML, but the assessment requires **PDF**. **Manually download 10 10-K PDFs**
into `data/pdfs/` (named `AAPL_2023.pdf`, …) and log each source URL + fiscal year in
`data/sources.csv`. Two free sources:

1. **SEC EDGAR (official, guaranteed real 10-K).**
   [EDGAR company search](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany) →
   filter filing type **10-K** → open the latest → open the primary `.htm` document →
   browser **Print → Save as PDF**. Unambiguously the real 10-K with the financial statements.
2. **Company Investor Relations sites / [annualreports.com](https://www.annualreports.com).** Most
   large-caps post the 10-K as a PDF directly — faster, but verify it's the actual Form 10-K (has the
   consolidated income statement, cash flow, and balance sheet), not just a glossy annual-report wrapper.

The 10 recommended large-caps (Apple, Microsoft, Alphabet, Amazon, Meta, NVIDIA, Intel, Cisco, Oracle,
Tesla) all publish 10-K PDFs on their IR pages.

> Automating EDGAR-HTML → PDF (Playwright headless print) is possible but adds Windows tooling pain for
> zero requirement benefit. **Out of scope** unless we later want a one-click refresh.

---

## 5. Ground truth

Manual, one-time, ~30 values. Read each PDF and record the **correct** value for the most recent fiscal
year, normalized to **absolute USD**.

`data/ground_truth.csv`:

| column | example | notes |
|---|---|---|
| `company` | `AAPL` | |
| `fiscal_year` | `2023` | the year we're extracting |
| `field` | `rd_expense` | `rd_expense` \| `capex` \| `long_term_debt` |
| `value_usd` | `29915000000` | canonical: absolute dollars |
| `unit_in_filing` | `millions` | what the statement reported in |
| `source_page` | `31` | PDF page — also used to spot-check extractions |
| `source_line` | `Research and development` | verbatim label, for disambiguation |

Capex stored as a **positive** magnitude; we decide once and apply the same sign convention to predictions.

---

## 6. Extraction pipeline

Same model for both iterations: **Google `gemini-2.5-flash` on the free tier** (no payment / no credit
card via Google AI Studio). It supports native PDF input, structured JSON output, and a 1M-token context
— everything the pipeline needs. Keep it fixed across v1/v2 so improvements come from the pipeline, not
the model. (Offline alternative: a local **Ollama** model — see §11. Whichever we pick, the model call
lives only in `src/llm.py`.) Both iterations output the same JSON shape so evaluation code is shared.

### Iteration 1 — naive baseline (designed to be wrong sometimes)

```
PDF ──pdfplumber──► full plain text ──► single LLM call ──► {3 raw numbers}
```

- `pdfplumber` flattens tables to text → columns misalign, multi-year numbers run together.
- Prompt is deliberately minimal: "Find R&D expense, capital expenditures, and long-term debt. Return
  JSON." No unit guidance, no fiscal-year pin, no citation.
- **Expected errors:** unit/scale mistakes, wrong fiscal-year column, wrong line item (e.g. total debt
  incl. current portion), occasional null/hallucination. These are the material for §7.

### Iteration 2 — targeted refinement

Driven by *what the error analysis finds* (§7). The planned levers, in priority order:

1. **Send the right pages, as native PDF, not flattened text.** Locate the three statements by searching
   for headers ("CONSOLIDATED STATEMENTS OF OPERATIONS", "...CASH FLOWS", "...BALANCE SHEETS"), then pass
   only those pages as a **PDF document block** so Claude reads the table structure visually instead of
   from mangled text.
2. **Structured output** (`output_config.format` with a JSON schema) so every field returns
   `{value, unit, fiscal_year, source_page, source_text}` — not a bare number.
3. **Disambiguating prompt:** state the target fiscal year explicitly, require the value for *that* year's
   column, define each field (e.g. "long-term debt excluding current portion"), and require the source
   line + page (PDF **citations**, `page_location`).
4. **Deterministic normalization step (code, not the model):** read the "(in thousands/millions)"
   qualifier and convert `value × scale → absolute USD`; enforce capex sign convention.

We won't necessarily ship all four — we ship the ones the error analysis says matter, and document the
ones we skipped and why. That *is* the iteration narrative.

### Shared output contract

`results/extraction_v1.csv`, `results/extraction_v2.csv` — same columns as `ground_truth.csv` plus
`raw_value`, `raw_unit`, `source_page`, `source_text`, `error` (if the call failed).

---

## 7. Evaluation & error analysis

### Metrics (`src/evaluate.py` → `results/metrics.csv`)

Compare normalized absolute-USD predicted vs truth.

- **Tolerance accuracy** — correct if relative error ≤ **0.5%** (absorbs rounding/disclosed-precision
  differences). Reported overall and **per field**.
- **MAPE** — mean absolute % error, to size *how wrong* the misses are (a 1000× unit error vs a
  rounding blip look identical under accuracy alone).
- **Counts per error category** (below).

### Error taxonomy (the heart of the project)

Every prediction that isn't "correct" gets exactly one label:

| Category | Definition | Likely fix |
|---|---|---|
| `unit_scale` | Right digits, wrong magnitude (×1,000 / ×1,000,000) | Normalization step (lever 4) |
| `wrong_period` | Picked a different fiscal-year column | Fiscal-year pin (lever 3) |
| `wrong_line_item` | Adjacent/related line (e.g. total debt vs LT debt) | Field definitions + citations (lever 3) |
| `missing` | Returned null though the value exists | Page targeting (lever 1) |
| `hallucinated` | Value not present in the filing | Citations force grounding (lever 2/3) |
| `rounding` | Off by < tolerance but flagged | Usually fine; informs tolerance choice |

**Methodology to present in the interview:**
1. Run v1 → diff against ground truth → auto-flag misses.
2. Hand-classify each miss into the taxonomy (it's only ~30 rows).
3. Find the **dominant category**, build v2's primary lever to kill it, leave the rest documented.
4. Re-run, re-classify, show the category histogram shrink.

---

## 8. The iteration story (what we'll actually narrate)

> v1 baseline (text + naive prompt) → measure → categorize errors → most are `unit_scale` and
> `wrong_period` → v2 adds page-targeted PDF input + fiscal-year-pinned structured prompt + a
> deterministic unit-normalization step → accuracy rises, the error histogram collapses toward
> `wrong_line_item` edge cases → discuss what a v3 would target.

This gives concrete before/after numbers and a clear cause→fix→effect chain, which is exactly what
requirements 5–7 ask for.

---

## 9. Dashboard (bonus) — Streamlit

`dashboard/app.py`, reading the CSVs in `results/`. Three views:

1. **Fields across companies** — grouped bar: R&D / capex / debt for all 10 companies (log scale).
2. **Accuracy by iteration** — v1 vs v2, overall and per field.
3. **Error breakdown** — stacked bar of error categories, v1 vs v2 (the shrink is the headline).
4. **Detail table** — per company/field: predicted vs truth, % error, category, source page link.

Plotly for charts. No callbacks/state beyond reading CSVs — keep it a thin viewer over the results.

---

## 10. Project structure

```
report-data-extraction-evaluation/
├── architecture.md            # this file
├── README.md                  # how to run
├── requirements.txt
├── .env                        # GEMINI_API_KEY (gitignored)
├── data/
│   ├── pdfs/                    # 10 downloaded 10-K PDFs
│   ├── sources.csv             # company, fiscal_year, source_url
│   └── ground_truth.csv        # manual labels
├── src/
│   ├── config.py               # companies, fields, model id, tolerance
│   ├── extract.py              # run v1/v2 over all PDFs → results CSV
│   ├── pdf_utils.py            # pdfplumber text + statement-page finder
│   ├── normalize.py            # unit/scale + sign normalization
│   └── evaluate.py             # metrics + error categorization
├── results/
│   ├── extraction_v1.csv
│   ├── extraction_v2.csv
│   └── metrics.csv
└── dashboard/
    └── app.py                  # Streamlit
```

---

## 11. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | ecosystem fit |
| LLM | `google-genai` SDK, `gemini-2.5-flash` (free tier, fixed) | free; native PDF/table reading; structured outputs; 1M context |
| PDF → text | `pdfplumber` | simple; its table-flattening *creates* v1's errors (a feature here) |
| PDF → model | native PDF (inline base64 / Gemini File API) for v2's targeted pages | preserves table structure for accurate reads |
| Schema/validation | `pydantic` → Gemini `responseSchema` | typed, validated extraction in v2 |
| LLM client | isolated in `src/llm.py` | one function `extract(pdf/text, prompt, schema)` → swap provider (Ollama/Claude) freely |
| Data | `pandas` + CSV | no DB needed for 30 rows |
| Dashboard | `streamlit` + `plotly` | fastest path to the bonus |

### Relevant Gemini API specifics (grounds the build)

- **PDF input:** pass the PDF as inline base64, or via the **File API** for larger files (Gemini handles
  up to ~1,000 pages). A full 10-K fits, but v2 sends **only the 3 statement pages** for accuracy + fewer
  tokens.
- **Structured output:** set `response_mime_type="application/json"` + a `response_schema` (built from a
  Pydantic model) → guaranteed-shape `{value, unit, fiscal_year, source_page, source_text}`. We put
  `source_page`/`source_text` directly in the schema, so grounding is built in — no separate citations
  API needed.
- **Free-tier limits:** generous daily request quota (hundreds–thousands/day) — far above this project's
  ~30 calls. The binding constraint is the **per-minute** rate limit; add a short `sleep` between calls
  if you hit it. No prompt caching needed on the free tier.
- **Token counting:** the SDK's `count_tokens` confirms a doc fits the context before a full run.

---

## 12. Cost & effort

- **$0 — Gemini free tier.** The whole project is ~30 extractions (10 docs × v1 + v2) plus a few reruns,
  far under the free tier's daily request limit.
- The real constraint is the **per-minute** rate limit, not cost — a 4–5s `sleep` between calls keeps us
  safe; a full 10-doc run still finishes in a couple of minutes.
- One call per document returns **all three fields** (the PDF is sent once) — fewer calls, simpler code.
- Effort, not money, is the cost here: the ~1–2 hrs of manual ground-truth labelling (§5, §13) is the
  main time sink.

---

## 13. Build order (milestones)

1. **Scaffold** — repo structure, `config.py`, download 10 PDFs, fill `sources.csv`.
2. **Ground truth** — hand-label `ground_truth.csv` (~1–2 hrs, the real time sink). Do this first; it
   anchors everything.
3. **v1 baseline** — `pdf_utils` + naive `extract.py` → `extraction_v1.csv`.
4. **Evaluate v1** — `evaluate.py` → metrics + categorized errors. *Confirm the first pass is imperfect.*
5. **Error analysis** — classify, find the dominant category, decide v2's lever(s).
6. **v2** — page targeting + structured/pinned prompt + normalization → `extraction_v2.csv`, re-evaluate.
7. **Dashboard** — Streamlit over the result CSVs.
8. **README + narrative** — wire up the run commands and the iteration story for the presentation.

---

## 14. Risks / things to watch

- **v1 too accurate** (opus reads tables well even from flattened text) → if accuracy is already high,
  swap in the harder geographic-revenue field (§3) or make v1 stricter (truncate text / no table hints).
- **Ground-truth mistakes** poison metrics → double-check each label against the cited page; the
  `source_page` column makes spot-checking fast.
- **Sign/convention drift** (capex negative, debt gross vs net) → fix conventions once in `normalize.py`
  and document them; apply identically to predictions and truth.
- **PDF size** > limits for a couple of filings → v2's page-targeting sidesteps this; for v1, cap text.
```
