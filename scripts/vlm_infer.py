#!/usr/bin/env python3
"""Run Qwen2.5-VL-3B on a gold split (zero-shot, or with a LoRA adapter) and store predictions.

  python scripts/vlm_infer.py --system zeroshot --split test
  python scripts/vlm_infer.py --system qlora --adapter data/adapters/qlora-v1 --split test
Greedy decoding, bf16, fixed batch size (changing the batch size can change outputs; keep it the same for every system).
Resumable: ids already in results/preds/<system>_<split>.jsonl are skipped.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import torch  # noqa: E402
from qwen_vl_utils import process_vision_info  # noqa: E402
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration  # noqa: E402

from invoicecheck.extraction import parse_model_json  # noqa: E402
from invoicecheck.vlm import MAX_PIXELS, MIN_PIXELS, MODEL_ID, messages  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--system", required=True)
ap.add_argument("--split", required=True)
ap.add_argument("--adapter", default=None)
ap.add_argument("--synth", default="data/synth")
ap.add_argument("--batch-size", type=int, default=8)
ap.add_argument("--max-new-tokens", type=int, default=900)
ap.add_argument("--limit", type=int, default=None)
ap.add_argument("--prompt-version", default="v2")
a = ap.parse_args()

gold = [json.loads(l) for l in open(f"{a.synth}/gold_{a.split}.jsonl", encoding="utf-8") if l.strip()]
if a.limit:
    gold = gold[:a.limit]
out_path = Path(f"results/preds/{a.system}_{a.split}.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)
done = {json.loads(l)["id"] for l in open(out_path, encoding="utf-8")} if out_path.exists() else set()
todo = [g for g in gold if g["invoice_id"] not in done]
print(f"{a.system}/{a.split}: {len(done)} done, {len(todo)} to do", flush=True)

proc = AutoProcessor.from_pretrained(MODEL_ID, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
proc.tokenizer.padding_side = "left"
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16, device_map="cuda")
if a.adapter:
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, a.adapter)
model.eval()

t0 = time.time()
with open(out_path, "a", encoding="utf-8") as f:
    for b in range(0, len(todo), a.batch_size):
        chunk = todo[b:b + a.batch_size]
        msgs = [messages(str(Path(a.synth).resolve() / g["image"]), a.prompt_version) for g in chunk]
        texts = [proc.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in msgs]
        images, _ = process_vision_info(msgs)
        inputs = proc(text=texts, images=images, padding=True, return_tensors="pt").to("cuda")
        with torch.no_grad():
            gen = model.generate(**inputs, max_new_tokens=a.max_new_tokens, do_sample=False)
        outs = proc.batch_decode([o[len(i):] for i, o in zip(inputs.input_ids, gen)], skip_special_tokens=True)
        for g, raw in zip(chunk, outs):
            f.write(json.dumps({"id": g["invoice_id"], "raw": raw, "parsed": parse_model_json(raw), "system": a.system,
                                "batch_size": a.batch_size, "max_pixels": MAX_PIXELS, "prompt_version": a.prompt_version}, ensure_ascii=False) + "\n")
        f.flush()
        print(f"{b + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
print("done", flush=True)
