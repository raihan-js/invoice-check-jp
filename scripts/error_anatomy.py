#!/usr/bin/env python3
"""Which check catches a corrupted registration number? Take real registered numbers, corrupt them the way an
extractor might (one wrong digit, or two adjacent digits swapped) and classify each result:

  check_digit   the 13 digits no longer form a valid corporate number
  lookup        valid check digit but the number is not in the registry
  other_company valid check digit AND registered to a different company (only a name match can catch this)
  unchanged     the 'corruption' left the number identical (adjacent equal digits), excluded from rates

Writes results/error_anatomy.json. Seeded; samples are drawn from all corporations in the cached registry snapshot.
  python scripts/error_anatomy.py --n 300000
"""
import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from invoicecheck.checkdigit import is_valid_corporate_number  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="data/registry/registry.sqlite")
ap.add_argument("--n", type=int, default=300000)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

rng = random.Random(a.seed)
con = sqlite3.connect(a.db)
regs = [r[0][1:] for r in con.execute("SELECT reg_no FROM registrants")]
known = set(regs)
sample = rng.sample(regs, a.n)


def classify(orig, bad):
    if bad == orig:
        return "unchanged"
    if not is_valid_corporate_number(bad):
        return "check_digit"
    return "other_company" if bad in known else "lookup"


def run(kind):
    out = {"check_digit": 0, "lookup": 0, "other_company": 0}
    for orig in sample:
        if kind == "substitute":
            pos = rng.randrange(13)
            d = rng.choice([c for c in "0123456789" if c != orig[pos]])
            bad = orig[:pos] + d + orig[pos + 1:]
        else:
            pos = rng.randrange(12)
            bad = orig[:pos] + orig[pos + 1] + orig[pos] + orig[pos + 2:]
        c = classify(orig, bad)
        if c != "unchanged":
            out[c] += 1
    n = sum(out.values())
    return {"n": n, **out, **{f"share_{k}": round(v / n, 5) for k, v in out.items()}}


res = {"registry_size": len(regs), "sample": a.n, "seed": a.seed,
       "one_wrong_digit": run("substitute"), "adjacent_swap": run("swap")}
for k in ("one_wrong_digit", "adjacent_swap"):
    r = res[k]
    surv = r["lookup"] + r["other_company"]
    r["survive_check_digit"] = surv
    r["share_of_survivors_on_other_company"] = round(r["other_company"] / surv, 4)
res["note"] = ("every single-digit substitution that survives the check digit is a 0<->9 swap (mod-9 weighted sum); most land on "
               "an unregistered number (caught by lookup) but a minority land on another registered company, far above chance "
               "because registered numbers are clustered, and only a name comparison can catch those")
Path("results/error_anatomy.json").write_text(json.dumps(res, indent=2) + "\n")
print(json.dumps(res, indent=1))
