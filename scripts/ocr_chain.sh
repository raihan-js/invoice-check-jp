#!/usr/bin/env bash
# OCR the test and hold-out splits for the OCR+rules baseline, one shard of N. Resumable (skips finished invoices).
#   setsid nohup bash scripts/ocr_chain.sh 0 2 > data/ocr_shard0.log 2>&1 < /dev/null &
set -u
cd "$(dirname "$0")/.."
K=${1:-0}; N=${2:-2}
for split in test holdout; do
  echo "STAGE ocr-$split-shard$K start $(date +%H:%M)"
  nice -n 10 .venv-ocr/bin/python scripts/run_ocr.py --split $split --shard $K/$N --cpu-threads 5
  echo "STAGE ocr-$split-shard$K done rc=$? $(date +%H:%M)"
done
echo "STAGE OCR-ALL-DONE shard$K $(date +%H:%M)"
