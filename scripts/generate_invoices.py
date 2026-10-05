#!/usr/bin/env python3
"""Generate the synthetic invoice dataset: images, gold JSONL per split, the synthetic registry, manifest and summary.

  python scripts/generate_invoices.py --out data/synth --train 3000 --val 300 --test 600 --holdout 200 --seed 0
Issuers are fictitious and disjoint across splits; names and numbers that exist in the real registry snapshot (if
data/registry/registry.sqlite is present) are rejected. Every rendered page is checked against its gold.
"""
import argparse
import json
import random
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from playwright.sync_api import sync_playwright  # noqa: E402

from invoicecheck.normalize import normalize_name  # noqa: E402
from invoicecheck.synth import names  # noqa: E402
from invoicecheck.synth.align import missing_values  # noqa: E402
from invoicecheck.synth.invoice import ISSUE_KINDS, make_invoice, tax_check  # noqa: E402
from invoicecheck.synth.issuers import build_issuers, build_registry, record_dict  # noqa: E402
from invoicecheck.synth.render import H, W, render_page  # noqa: E402
from invoicecheck.synth.skins import HOLDOUT_TEMPLATES, TRAIN_TEMPLATES, layout_of  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="data/synth")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--train", type=int, default=3000)
ap.add_argument("--val", type=int, default=300)
ap.add_argument("--test", type=int, default=600)
ap.add_argument("--holdout", type=int, default=200)
ap.add_argument("--issue-rate", type=float, default=0.12, help="share of invoices with one injected document issue")
ap.add_argument("--no-real-check", action="store_true")
a = ap.parse_args()

rng = random.Random(a.seed)
out = Path(a.out)
counts = {"train": a.train, "val": a.val, "test": a.test, "holdout": a.holdout}
real_nums, real_names = frozenset(), frozenset()
db = Path("data/registry/registry.sqlite")
if db.exists() and not a.no_real_check:
    con = sqlite3.connect(db)
    real_nums = frozenset(r[0] for r in con.execute("SELECT reg_no FROM registrants"))
    real_names = frozenset(normalize_name(r[0]) for r in con.execute("SELECT name FROM registrants"))
    print(f"real registry loaded for rejection: {len(real_nums):,} numbers, {len(real_names):,} names", flush=True)

issuer_counts = {s: max(8, n // 8) for s, n in counts.items()}
issuers = build_issuers(rng, issuer_counts, real_nums, real_names)
registry = build_registry(rng, issuers, 3000, real_nums, real_names)
by_split = {s: [i for i in issuers if i.split == s] for s in counts}
recipients = names.unique_company_names(rng, 600, real_names | {normalize_name(i.name) for i in issuers})

(out / "images").mkdir(parents=True, exist_ok=True)
with open(out / "registry_synthetic.jsonl", "w", encoding="utf-8") as f:
    for r in registry:
        f.write(json.dumps(record_dict(r), ensure_ascii=False) + "\n")

summary = {"seed": a.seed, "counts": counts, "by_template": Counter(), "by_issue": Counter(), "tax_checker_clean_pass": 0,
           "tax_checker_clean_total": 0, "alignment_failures": [], "overflow_failures": [], "seal_overlap": 0, "layout": Counter()}
idx = 0
t0 = time.time()
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.25)
    for split, n in counts.items():
        pool = by_split[split]
        templates = HOLDOUT_TEMPLATES if split == "holdout" else TRAIN_TEMPLATES
        gold_f = open(out / f"gold_{split}.jsonl", "w", encoding="utf-8")
        for k in range(n):
            tpl = templates[k % len(templates)]
            issue = rng.choice(ISSUE_KINDS) if rng.random() < a.issue_rate else None
            g = make_invoice(rng, idx, split, rng.choice(pool), rng.choice(recipients), tpl, registry, issue=issue)
            g["layout"] = layout_of(tpl)
            path = out / "images" / split / f"{g['invoice_id']}.jpg"
            text, fits = render_page(page, g, path, rng)
            g["image"] = f"images/{split}/{g['invoice_id']}.jpg"
            missing = missing_values(g, text)
            if missing:
                summary["alignment_failures"].append({"id": g["invoice_id"], "template": tpl, "missing": missing[:4]})
            if not fits:
                summary["overflow_failures"].append({"id": g["invoice_id"], "template": tpl})
            if not g["document_issues"]:
                summary["tax_checker_clean_total"] += 1
                summary["tax_checker_clean_pass"] += int(tax_check(g).ok)
            summary["by_template"][tpl] += 1
            summary["by_issue"][issue or "none"] += 1
            summary["layout"][g["layout"]] += 1
            summary["seal_overlap"] += int(g["seal_overlap"])
            gold_f.write(json.dumps(g, ensure_ascii=False) + "\n")
            idx += 1
            if idx % 200 == 0:
                print(f"{idx} rendered, {time.time() - t0:.0f}s, alignment failures {len(summary['alignment_failures'])}, overflow {len(summary['overflow_failures'])}", flush=True)
        gold_f.close()
    browser.close()

for k in ("by_template", "by_issue", "layout"):
    summary[k] = dict(summary[k])
summary["total"] = idx
summary["elapsed_s"] = round(time.time() - t0)
Path("results").mkdir(exist_ok=True)
Path("results/synth_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
(out / "manifest.json").write_text(json.dumps({"seed": a.seed, "counts": counts, "train_templates": TRAIN_TEMPLATES, "holdout_templates": HOLDOUT_TEMPLATES,
                                               "issue_kinds": ISSUE_KINDS, "issue_rate": a.issue_rate, "page_px": [W, H], "device_scale_factor": 1.25}, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("total", "elapsed_s", "tax_checker_clean_pass", "tax_checker_clean_total")}), "alignment failures:",
      len(summary["alignment_failures"]), "overflow failures:", len(summary["overflow_failures"]), flush=True)
