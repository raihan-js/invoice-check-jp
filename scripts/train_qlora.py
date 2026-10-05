#!/usr/bin/env python3
"""QLoRA fine-tune Qwen2.5-VL-3B on the synthetic training split. Resumes from the latest checkpoint automatically.

  python scripts/train_qlora.py --out data/adapters/qlora-v1 --epochs 1
4-bit NF4 base, LoRA on the language model only (the vision tower is frozen), loss on the answer tokens only, batch size 1 with
gradient accumulation, image budget capped at MAX_PIXELS (reported with the results).
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")   # the 3060 is close to its limit on 7-item invoices
import torch  # noqa: E402
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training  # noqa: E402
from qwen_vl_utils import process_vision_info  # noqa: E402
from transformers import (AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration, Trainer,  # noqa: E402
                          TrainingArguments)

from invoicecheck.extraction import gold_to_target  # noqa: E402
from invoicecheck.vlm import MAX_PIXELS, MIN_PIXELS, MODEL_ID, messages  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--synth", default="data/synth")
ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--grad-accum", type=int, default=16)
ap.add_argument("--rank", type=int, default=16)
ap.add_argument("--limit", type=int, default=None)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

rows = [json.loads(l) for l in open(f"{a.synth}/gold_train.jsonl", encoding="utf-8") if l.strip()]
if a.limit:
    rows = rows[:a.limit]
proc = AutoProcessor.from_pretrained(MODEL_ID, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL_ID, quantization_config=bnb, torch_dtype=torch.bfloat16, device_map="cuda")
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
lora = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                  target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)")
model = get_peft_model(model, lora)
model.print_trainable_parameters()


class DS(torch.utils.data.Dataset):
    def __len__(self):
        return len(rows)

    def __getitem__(self, i):
        g = rows[i]
        msgs = messages(str(Path(a.synth).resolve() / g["image"]))
        answer = json.dumps(gold_to_target(g), ensure_ascii=False)
        prompt = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        images, _ = process_vision_info(msgs)
        p = proc(text=[prompt], images=images, return_tensors="pt")
        full = proc(text=[prompt + answer + "<|im_end|>\n"], images=images, return_tensors="pt")
        labels = full["input_ids"].clone()
        labels[:, :p["input_ids"].shape[1]] = -100
        return {**{k: v.squeeze(0) if k in ("input_ids", "attention_mask") else v for k, v in full.items()}, "labels": labels.squeeze(0)}


def collate(batch):
    assert len(batch) == 1
    b = batch[0]
    return {k: (v.unsqueeze(0) if k in ("input_ids", "attention_mask", "labels") else v) for k, v in b.items()}


args = TrainingArguments(output_dir=a.out, per_device_train_batch_size=1, gradient_accumulation_steps=a.grad_accum, num_train_epochs=a.epochs,
                         learning_rate=a.lr, lr_scheduler_type="cosine", warmup_steps=0.03, bf16=True, logging_steps=5, save_steps=50,
                         report_to="none", remove_unused_columns=False, gradient_checkpointing=True, seed=a.seed,
                         gradient_checkpointing_kwargs={"use_reentrant": False}, dataloader_num_workers=2)
trainer = Trainer(model=model, args=args, train_dataset=DS(), data_collator=collate)
has_ckpt = any(Path(a.out).glob("checkpoint-*")) if Path(a.out).exists() else False
trainer.train(resume_from_checkpoint=True if has_ckpt else None)
model.save_pretrained(a.out + "/final")
print("saved", a.out + "/final")
