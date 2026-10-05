#!/usr/bin/env python3
"""Run the rule engine on perfect-OCR text boxes taken from the page DOM (the upper bound for the 'OCR + rules' baseline).
  python scripts/run_rules.py --split test            # writes results/preds/rules_dom_<split>.jsonl
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from playwright.sync_api import sync_playwright  # noqa: E402

from invoicecheck.rules import extract  # noqa: E402
from invoicecheck.synth.render import H, W, build_blocks, dom_lines, render_html  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--split", required=True)
ap.add_argument("--synth", default="data/synth")
ap.add_argument("--limit", type=int, default=None)
a = ap.parse_args()
gold = [json.loads(l) for l in open(f"{a.synth}/gold_{a.split}.jsonl", encoding="utf-8") if l.strip()]
if a.limit:
    gold = gold[:a.limit]
out = Path(f"results/preds/rules_dom_{a.split}.jsonl")
out.parent.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p, open(out, "w", encoding="utf-8") as f:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": W, "height": H})
    for g in gold:
        pg.set_content(render_html(g, random.Random(g["invoice_id"])))
        f.write(json.dumps({"id": g["invoice_id"], "parsed": extract(dom_lines(pg)), "system": "rules_dom"}, ensure_ascii=False) + "\n")
    b.close()
print("wrote", out, len(gold))
