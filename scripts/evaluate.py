#!/usr/bin/env python3
"""Score predictions (results/preds/<system>_<split>.jsonl) against gold (data/synth/gold_<split>.jsonl).

  python scripts/evaluate.py --system zeroshot --split test
Prints a markdown row and writes results/eval_<system>_<split>.json. Missing predictions count as failures.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from invoicecheck.evaluation import evaluate, format_row, load_jsonl, summarise, write_summary  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--system", required=True)
ap.add_argument("--split", required=True)
ap.add_argument("--synth", default="data/synth")
a = ap.parse_args()
gold = load_jsonl(f"{a.synth}/gold_{a.split}.jsonl")
preds = load_jsonl(f"results/preds/{a.system}_{a.split}.jsonl")
summary = summarise(evaluate(gold, preds))
write_summary(a.system, a.split, summary)
print(format_row(f"{a.system} / {a.split}", summary))
print({k: round(v["mean"], 3) for k, v in summary["exact_by_layout"].items()}, "exact by layout")
