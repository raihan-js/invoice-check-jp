#!/usr/bin/env python3
"""Learning curve on the first 150 validation invoices: zero-shot (0 training invoices) and QLoRA checkpoints 50/100/150/final
(16 invoices per optimizer step: 800, 1,600, 2,400, 3,000). Writes results/learning_curve.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from invoicecheck.evaluation import evaluate, load_jsonl, summarise  # noqa: E402

gold = load_jsonl("data/synth/gold_val.jsonl")[:150]
points = [("zeroshot", 0), ("qlora_ckpt50", 800), ("qlora_ckpt100", 1600), ("qlora_ckpt150", 2400), ("qlora", 3000)]
out = []
for name, n_train in points:
    recs = evaluate(gold, load_jsonl(f"results/preds/{name}_val.jsonl"))
    s = summarise(recs)
    out.append({"system": name, "training_invoices": n_train, "exact": s["exact"], "by_layout": s["exact_by_layout"],
                "covered_exact": sum(r["covered_exact"] for r in recs) / len(recs), "fields": {k: v["mean"] for k, v in s["fields"].items()}})
Path("results/learning_curve.json").write_text(json.dumps(out, indent=2) + "\n")
print("| training invoices | exact | horizontal | vertical | covered fields all correct |\n|---|---|---|---|---|")
for o in out:
    l = o["by_layout"]
    print(f"| {o['training_invoices']} | {100 * o['exact']['mean']:.1f} [{100 * o['exact']['lo']:.1f}, {100 * o['exact']['hi']:.1f}] | "
          f"{100 * l['horizontal']['mean']:.1f} | {100 * l['vertical']['mean']:.1f} | {100 * o['covered_exact']:.1f} |")
