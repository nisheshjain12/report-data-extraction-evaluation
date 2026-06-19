"""
Score extraction results against the hand-checked ground truth.

Canonical unit = millions (how the statements report, and our ground_truth
'value_millions'). A prediction is CORRECT if within TOLERANCE of the truth.
Misses are categorized so we can see WHAT went wrong:

  correct     - within tolerance
  unit_scale  - right digits, wrong scale (e.g. dollars instead of millions)
  missing     - model returned null / nothing
  wrong       - wrong number (wrong line item, wrong period, or hallucination)

Outputs:
  results/scored.csv   - every prediction with truth, category, correct flag
  results/metrics.csv  - accuracy per version, per field, and category counts

Run: python src/evaluate.py
"""

import pandas as pd

import config

TOL = config.TOLERANCE
SCALES = [1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9]   # scales we treat as "unit" mistakes


def categorize(pred, truth):
    """Return (category, is_correct) for one prediction vs its truth."""
    if pred is None or (isinstance(pred, float) and pd.isna(pred)):
        return "missing", False
    try:
        pred = float(pred)
    except (TypeError, ValueError):
        return "missing", False
    if truth and abs(pred - truth) / abs(truth) <= TOL:
        return "correct", True
    for s in SCALES:                                  # right number, wrong scale?
        if truth and abs(pred / s - truth) / abs(truth) <= TOL:
            return "unit_scale", False
    return "wrong", False


def score_file(path, gt):
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        truth = gt.get((r["company"], r["field"]))
        cat, ok = categorize(r.get("predicted"), truth)
        rows.append({
            "version": r.get("version", path.stem),
            "company": r["company"], "field": r["field"],
            "predicted": r.get("predicted"), "truth": truth,
            "category": cat, "correct": ok,
        })
    return pd.DataFrame(rows)


def main():
    gt_df = pd.read_csv(config.GROUND_TRUTH)
    gt = {(r.company, r.field): r.value_millions for r in gt_df.itertuples()}

    frames = []
    for name in ["extraction_v1.csv", "extraction_v2.csv"]:   # score whichever exist
        path = config.RESULTS_DIR / name
        if path.exists():
            frames.append(score_file(path, gt))
    scored = pd.concat(frames, ignore_index=True)
    scored.to_csv(config.RESULTS_DIR / "scored.csv", index=False)

    metrics = []
    for ver, g in scored.groupby("version"):
        row = {"version": ver, "accuracy": round(g["correct"].mean(), 3), "n": len(g)}
        for field in config.FIELDS:                      # per-field accuracy
            gf = g[g.field == field]
            row[field] = round(gf["correct"].mean(), 3) if len(gf) else None
        for cat in ["correct", "unit_scale", "missing", "wrong"]:  # error counts
            row[f"#{cat}"] = int((g.category == cat).sum())
        metrics.append(row)
    mdf = pd.DataFrame(metrics)
    mdf.to_csv(config.RESULTS_DIR / "metrics.csv", index=False)

    print("=== metrics ===")
    print(mdf.to_string(index=False))
    print("\n=== misses ===")
    misses = scored[~scored.correct][["version", "company", "field", "predicted", "truth", "category"]]
    print(misses.to_string(index=False) if len(misses) else "none!")


if __name__ == "__main__":
    main()
