#!/usr/bin/env python3
"""Build the local SQLite registry cache from the NTA corporate CSV files and write results/registry_provenance.json.

  python scripts/build_registry_db.py --csv-dir data/registry/csv --snapshot 2026-09-30 --downloaded 2026-10-05
Also measures the corporate-number check-digit pass rate over every registered corporation (results/registry_checkdigit.json).
"""
import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from invoicecheck.checkdigit import is_valid_registration_number  # noqa: E402
from invoicecheck.registry import build_db, save_provenance  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--csv-dir", default="data/registry/csv")
ap.add_argument("--db", default="data/registry/registry.sqlite")
ap.add_argument("--snapshot", required=True)
ap.add_argument("--downloaded", required=True)
a = ap.parse_args()

paths = sorted(glob.glob(f"{a.csv_dir}/h_all_*.csv"))
assert paths, "no h_all_*.csv files found"
meta = build_db(paths, a.db, a.snapshot, a.downloaded)
save_provenance(meta, "results/registry_provenance.json")
print(json.dumps(meta, ensure_ascii=False, indent=1))

con = sqlite3.connect(a.db)
total = bad = 0
examples = []
for (reg,) in con.execute("SELECT reg_no FROM registrants"):
    total += 1
    if not is_valid_registration_number(reg):
        bad += 1
        if len(examples) < 5:
            examples.append(reg)
res = {"registrants_checked": total, "check_digit_valid": total - bad, "check_digit_invalid": bad,
       "invalid_examples": examples, "snapshot": a.snapshot}
Path("results/registry_checkdigit.json").write_text(json.dumps(res, indent=2) + "\n")
print(json.dumps(res, indent=1))
