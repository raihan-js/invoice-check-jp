#!/usr/bin/env bash
# Resumable GPU chain for Invoice-Check JP: zero-shot baseline, QLoRA fine-tune, fine-tuned inference, learning curve.
# Start:  cd invoice-check-jp && setsid nohup bash scripts/gpu_chain.sh > data/gpu_chain.log 2>&1 < /dev/null &
# Watch:  grep STAGE data/gpu_chain.log
# Every stage skips itself if its output is already complete, so re-running after a power cut or a crash continues where it stopped.
set -u
cd "$(dirname "$0")/.."
PY=.venv-ml/bin/python
stage() { echo "STAGE $1 $2 $(date +%H:%M)"; }
need() { f=results/preds/$1_$2.jsonl; [ -f "$f" ] && [ "$(wc -l < "$f")" -ge "$3" ]; }   # system split n
infer() {   # system split n [adapter] [limit]
  if need "$1" "$2" "$3"; then stage "$1-$2" "skip (done)"; return; fi
  stage "$1-$2" start
  args="--system $1 --split $2"; [ -n "${4:-}" ] && args="$args --adapter $4"; [ -n "${5:-}" ] && args="$args --limit $5"
  $PY scripts/vlm_infer.py $args; stage "$1-$2" "done rc=$?"
}
infer zeroshot test 600
infer zeroshot holdout 200
infer zeroshot val 150 "" 150
if [ ! -d data/adapters/qlora-v1/final ]; then
  for try in 1 2 3; do
    stage train "start try $try"
    $PY scripts/train_qlora.py --out data/adapters/qlora-v1 --epochs 1; stage train "done rc=$?"
    [ -d data/adapters/qlora-v1/final ] && break
  done
else stage train "skip (done)"; fi
infer qlora test 600 data/adapters/qlora-v1/final
infer qlora holdout 200 data/adapters/qlora-v1/final
infer qlora val 150 data/adapters/qlora-v1/final 150
for ck in 50 100 150; do
  [ -d data/adapters/qlora-v1/checkpoint-$ck ] && infer qlora_ckpt$ck val 150 data/adapters/qlora-v1/checkpoint-$ck 150
done
stage ALL-DONE ""
