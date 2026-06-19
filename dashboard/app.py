"""
Dashboard for the 10-K extraction project.

Run from the project root:
    streamlit run dashboard/app.py

Reads the CSVs in results/ and data/ — it's a thin viewer, so re-running the
pipeline (extract + evaluate) and refreshing the page updates everything.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Make src/ importable so we reuse the same paths/field list as the pipeline.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import config  # noqa: E402

st.set_page_config(page_title="10-K Extraction", layout="wide")
st.title("10-K Data Extraction & Evaluation")

# --- load data ----------------------------------------------------------------
metrics = pd.read_csv(config.RESULTS_DIR / "metrics.csv")
scored = pd.read_csv(config.RESULTS_DIR / "scored.csv")
truth = pd.read_csv(config.GROUND_TRUTH)

# headline numbers
cols = st.columns(len(metrics))
for col, row in zip(cols, metrics.itertuples()):
    col.metric(f"{row.version} accuracy", f"{row.accuracy:.0%}")

# --- 1. accuracy: v1 vs v2 (overall + per field) ------------------------------
st.header("1 · Accuracy by iteration")
acc = metrics.melt(
    id_vars="version",
    value_vars=["accuracy", "rd_expense", "capex", "long_term_debt"],
    var_name="metric", value_name="accuracy",
)
st.plotly_chart(
    px.bar(acc, x="metric", y="accuracy", color="version", barmode="group",
           text_auto=".0%", title="v1 vs v2 — overall and per-field accuracy"),
    use_container_width=True,
)

# --- 2. error categories: v1 vs v2 --------------------------------------------
st.header("2 · Error breakdown (what went wrong)")
cats = metrics.melt(
    id_vars="version",
    value_vars=["#correct", "#unit_scale", "#missing", "#wrong"],
    var_name="category", value_name="count",
)
st.plotly_chart(
    px.bar(cats, x="version", y="count", color="category", text_auto=True,
           title="Predictions by category per iteration"),
    use_container_width=True,
)

# --- 3. the three fields across all companies (from ground truth) -------------
st.header("3 · Extracted values across companies")
field = st.selectbox("Field", list(config.FIELDS))
sub = truth[truth.field == field].sort_values("value_millions", ascending=False)
st.plotly_chart(
    px.bar(sub, x="company", y="value_millions",
           title=f"{field} — $millions (ground truth)"),
    use_container_width=True,
)

# --- 4. prediction detail table -----------------------------------------------
st.header("4 · Prediction detail")
version = st.radio("Version", sorted(scored.version.unique()), horizontal=True)
view = scored[scored.version == version].copy()
st.dataframe(
    view[["company", "field", "predicted", "truth", "category", "correct"]],
    use_container_width=True, hide_index=True,
)
