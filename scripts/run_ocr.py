#!/usr/bin/env python3
"""Run PaddleOCR (Japanese, PP-OCRv6) over a gold split and save raw text boxes: data/ocr/<split>/<invoice_id>.json.
  .venv-ocr/bin/python scripts/run_ocr.py --split train --limit 100
Resumable. CPU only (MKLDNN disabled: Paddle 3 fails on oneDNN with this model). Boxes are axis-aligned [x0, y0, x1, y1] in image pixels.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
from paddleocr import PaddleOCR  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--split", required=True)
ap.add_argument("--synth", default="data/synth")
ap.add_argument("--limit", type=int, default=None)
ap.add_argument("--shard", default="0/1", help="K/N: process every N-th invoice starting at K (parallel runs)")
ap.add_argument("--cpu-threads", type=int, default=5)
a = ap.parse_args()
gold = [json.loads(l) for l in open(f"{a.synth}/gold_{a.split}.jsonl", encoding="utf-8") if l.strip()]
if a.limit:
    gold = gold[:a.limit]
k, n = (int(x) for x in a.shard.split("/"))
gold = gold[k::n]
out_dir = Path(f"data/ocr/{a.split}")
out_dir.mkdir(parents=True, exist_ok=True)
todo = [g for g in gold if not (out_dir / f"{g['invoice_id']}.json").exists()]
print(f"ocr {a.split}: {len(gold) - len(todo)} done, {len(todo)} to do", flush=True)
ocr = PaddleOCR(lang="japan", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True, enable_mkldnn=False, cpu_threads=a.cpu_threads)
t0 = time.time()
for i, g in enumerate(todo, 1):
    r = ocr.predict(f"{a.synth}/{g['image']}")[0]
    lines = []
    for tx, bx in zip(r["rec_texts"], r["rec_boxes"]):
        x0, y0, x1, y1 = [float(v) for v in bx.tolist()]
        lines.append({"text": tx, "box": [x0, y0, x1, y1], "vertical": (y1 - y0) > 1.8 * (x1 - x0) and len(tx) > 2})
    (out_dir / f"{g['invoice_id']}.json").write_text(json.dumps(lines, ensure_ascii=False))
    if i % 20 == 0:
        print(f"{i}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
print("done", flush=True)
