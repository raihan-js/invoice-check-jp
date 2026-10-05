"""Evaluate extraction predictions against gold: per-field accuracy, whole-invoice exact match, slices, bootstrap CIs."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .extraction import FIELDS, gold_to_target, score


def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial interval for k successes in n trials (valid at k = 0 and k = n, where the bootstrap degenerates)."""
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def bootstrap_ci(values, n_boot=2000, seed=0, alpha=0.05):
    """Mean and percentile bootstrap interval of a 0/1 (or float) vector. For 0/1 vectors the exact Clopper-Pearson interval is
    added (cp_lo, cp_hi, k) and is the one to quote when the count is 0 or n."""
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n_boot, len(v)))
    means = v[idx].mean(axis=1)
    out = {"n": len(v), "mean": float(v.mean()), "lo": float(np.quantile(means, alpha / 2)), "hi": float(np.quantile(means, 1 - alpha / 2))}
    if set(np.unique(v)) <= {0.0, 1.0}:
        k = int(v.sum())
        out["k"] = k
        out["cp_lo"], out["cp_hi"] = clopper_pearson(k, len(v), alpha)
    return out


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def evaluate(gold_rows, pred_rows):
    """gold_rows: gold invoices; pred_rows: {id, parsed}. Missing predictions count as failures (parsed = None)."""
    preds = {p["id"]: p.get("parsed") for p in pred_rows}
    recs = []
    for g in gold_rows:
        r = score(preds.get(g["invoice_id"]), gold_to_target(g))
        recs.append({"id": g["invoice_id"], "template": g["template"], "layout": g["layout"], "seal_overlap": g["seal_overlap"],
                     "has_issue": bool(g["document_issues"]), "have_pred": g["invoice_id"] in preds, **r})
    return recs


def summarise(recs):
    out = {"n": len(recs), "predicted": sum(r["have_pred"] for r in recs), "parsed_json": sum(r["parsed"] for r in recs),
           "exact": bootstrap_ci([r["exact"] for r in recs]),
           "fields": {f: bootstrap_ci([r["fields"][f] for r in recs]) for f in FIELDS},
           "items_level": bootstrap_ci([r["items_correct"] / max(r["items_total"], 1) for r in recs])}
    for key in ("layout", "seal_overlap", "has_issue"):
        groups = defaultdict(list)
        for r in recs:
            groups[str(r[key])].append(r["exact"])
        out[f"exact_by_{key}"] = {k: bootstrap_ci(v) for k, v in sorted(groups.items())}
    by_t = defaultdict(list)
    for r in recs:
        by_t[r["template"]].append(r["exact"])
    out["exact_by_template"] = {k: bootstrap_ci(v)["mean"] for k, v in sorted(by_t.items())}
    return out


def format_row(name, s):
    e = s["exact"]
    f = lambda c: f"{100 * c['mean']:.1f}" if c["mean"] is not None else "-"
    return (f"| {name} | {s['n']} | {f(e)} [{100 * e['lo']:.1f}, {100 * e['hi']:.1f}] | " +
            " | ".join(f(s["fields"][k]) for k in FIELDS) + " |")


def write_summary(system, split, summary, out_dir="results"):
    Path(out_dir).mkdir(exist_ok=True)
    Path(out_dir, f"eval_{system}_{split}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
