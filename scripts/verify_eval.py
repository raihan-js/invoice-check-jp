#!/usr/bin/env python3
"""Verification-layer metrics for one system: automation rate vs residual error, per cumulative layer.
  python scripts/verify_eval.py --system zeroshot --split test
Uses the synthetic registry published with the dataset (data/synth/registry_synthetic.jsonl). Writes results/verification_<system>_<split>.json.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from invoicecheck.evaluation import load_jsonl  # noqa: E402
from invoicecheck.registry import Record, Registry  # noqa: E402
from invoicecheck.verification_eval import evaluate_verification, format_levels  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--system", required=True)
ap.add_argument("--split", required=True)
ap.add_argument("--synth", default="data/synth")
ap.add_argument("--limit", type=int, default=None)
a = ap.parse_args()
gold = load_jsonl(f"{a.synth}/gold_{a.split}.jsonl")
if a.limit:
    gold = gold[:a.limit]
preds = {p["id"]: p.get("parsed") for p in load_jsonl(f"results/preds/{a.system}_{a.split}.jsonl")}
registry = Registry.from_records([Record(**r) for r in load_jsonl(f"{a.synth}/registry_synthetic.jsonl")])
res = evaluate_verification(gold, preds, registry)
Path("results").mkdir(exist_ok=True)
Path(f"results/verification_{a.system}_{a.split}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
print(f"{a.system} / {a.split}: n={res['n']} (clean {res['n_clean']}, with a document issue {res['n_issue']})")
print(format_levels(res))
print("wrong extractions, first check that caught them:", res["wrong_extractions_by_first_check"])
print("approved but wrong, by field:", res["approved_but_wrong_by_field"])
print("injected issue caught by the intended check:", {k: (round(v["mean"], 2), v["n"]) for k, v in res["issue_caught_by_intended_check"].items()},
      "| all:", round(res["issue_caught_by_intended_check_all"]["mean"], 3))
