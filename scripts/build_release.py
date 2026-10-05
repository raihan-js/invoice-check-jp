#!/usr/bin/env python3
"""Stage the release packages locally (no network): data/release/dataset and data/release/adapter. Upload is a separate, explicit step.
  python scripts/build_release.py
"""
import json
import shutil
from pathlib import Path

R = Path("data/release")
if R.exists():
    shutil.rmtree(R)
ds, ad = R / "dataset", R / "adapter"
ds.mkdir(parents=True)
ad.mkdir(parents=True)

# dataset: images + gold + synthetic registry + manifest + card
shutil.copytree("data/synth/images", ds / "images")
for f in ("gold_train.jsonl", "gold_val.jsonl", "gold_test.jsonl", "gold_holdout.jsonl", "registry_synthetic.jsonl", "manifest.json"):
    shutil.copy(Path("data/synth") / f, ds / f)
shutil.copy("docs/DATASET_CARD.md", ds / "README.md")

# adapter: weights + config + card + attribution notice
src = Path("data/adapters/qlora-v1/final")
for f in ("adapter_config.json", "adapter_model.safetensors"):
    shutil.copy(src / f, ad / f)
t = json.load(open("results/eval_qlora_test.json")); h = json.load(open("results/eval_qlora_holdout.json"))
v = json.load(open("results/verification_qlora_test.json"))["levels"]["tax"]
ci = lambda c: f"{100 * c['mean']:.1f}% [{100 * c['lo']:.1f}, {100 * c['hi']:.1f}]"
(ad / "README.md").write_text(f"""---
base_model: Qwen/Qwen2.5-VL-3B-Instruct
library_name: peft
license: other
license_name: qwen-research
license_link: https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE
language: [ja]
tags: [qlora, lora, invoice, japanese, document-ai, vision-language]
datasets: [raihan-js/invoice-check-jp]
---

# Invoice-Check JP: Qwen2.5-VL-3B LoRA adapter

LoRA adapter (r=16, language model only, 29.9M trainable parameters) for extracting the fields of Japanese qualified invoices (適格請求書) from an image into JSON. Trained with QLoRA on 3,000 **synthetic** invoices; meant to be used together with the verification layer in https://github.com/raihan-js/invoice-check-jp, never on its own.

**License: non-commercial research use only.** This adapter is derived from Qwen2.5-VL-3B-Instruct (Qwen Research License). Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved.

## Results (synthetic data only)

| split | whole-invoice exact match [95% CI] |
|---|---|
| test (600 invoices, unseen issuers) | {ci(t['exact'])} |
| hold-out (200 invoices, unseen layouts) | {ci(h['exact'])} |

With the full check rule on the test split, {100 * v['automation_rate']['mean']:.1f}% of clean invoices are auto-approved and {v['residual_covered_among_approved']['k']} of {v['residual_covered_among_approved']['n']} approved invoices had a wrong field that a check can catch. Horizontal layouts 97.3% exact; vertical (縦書き) 40.0%, and 4% on an unseen fully vertical layout.

## Use

```python
import torch
from peft import PeftModel
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
base = "Qwen/Qwen2.5-VL-3B-Instruct"
proc = AutoProcessor.from_pretrained(base, min_pixels=256 * 28 * 28, max_pixels=1003520)
model = PeftModel.from_pretrained(Qwen2_5_VLForConditionalGeneration.from_pretrained(base, torch_dtype=torch.bfloat16, device_map="cuda"), "raihan-js/invoice-check-jp-qwen2.5-vl-3b-lora")
```
The prompt and image budget are in `src/invoicecheck/vlm.py` of the code repository (prompt v2). Greedy decoding.

## Limitations

Trained and evaluated on synthetic invoices only (fictitious issuers, 6 layouts); no evidence on real invoices. Weak on vertical layouts (sideways Latin text, rotated tables). Corporations only. Output must be verified before use: see the code repository.
""")
(ad / "NOTICE").write_text("Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved.\n")
size = lambda p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6
print(f"dataset {size(ds):.0f} MB, {len(list((ds / 'images').rglob('*.jpg')))} images; adapter {size(ad):.0f} MB; files: {sorted(p.name for p in ad.iterdir())}")
