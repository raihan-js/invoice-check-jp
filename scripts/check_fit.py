#!/usr/bin/env python3
"""Fast layout QA: re-render every gold invoice's HTML (no images, no noise) and report any whose content does not fit the page.
  python scripts/check_fit.py --synth data/synth
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from playwright.sync_api import sync_playwright  # noqa: E402

from invoicecheck.synth.render import H, W, render_html  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--synth", default="data/synth")
a = ap.parse_args()
gold = [json.loads(l) for sp in ("train", "val", "test", "holdout") for l in open(f"{a.synth}/gold_{sp}.jsonl", encoding="utf-8") if l.strip()]
bad = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": W, "height": H})
    for g in gold:
        pg.set_content(render_html(g, random.Random(g["invoice_id"])))
        if not pg.evaluate("() => { const e = document.querySelector('.page'); return e.scrollHeight <= e.clientHeight + 1 && e.scrollWidth <= e.clientWidth + 1; }"):
            bad.append((g["invoice_id"], g["template"], len(g["items"])))
    b.close()
print(f"{len(gold)} invoices checked, {len(bad)} do not fit", Counter(t for _, t, _ in bad), bad[:6])
