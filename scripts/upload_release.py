#!/usr/bin/env python3
"""Upload the staged release packages to Hugging Face and verify them (sizes must match). Run scripts/build_release.py first.
  .venv-ml/bin/python scripts/upload_release.py
Token: ~/.cache/huggingface/token (never printed).
"""
import sys
from pathlib import Path

from huggingface_hub import HfApi

T = (Path.home() / ".cache/huggingface/token").read_text().strip()
api = HfApi(token=T)
TARGETS = [("raihan-js/invoice-check-jp", "dataset", Path("data/release/dataset")),
           ("raihan-js/invoice-check-jp-qwen2.5-vl-3b-lora", "model", Path("data/release/adapter"))]
for repo, kind, folder in TARGETS:
    api.create_repo(repo, repo_type=kind, private=False, exist_ok=True)
    print("uploading", folder, "->", repo, flush=True)
    if kind == "dataset":
        api.upload_large_folder(repo_id=repo, repo_type=kind, folder_path=str(folder))
    else:
        api.upload_folder(repo_id=repo, repo_type=kind, folder_path=str(folder), commit_message="LoRA adapter, model card, Qwen attribution notice")
ok = True
for repo, kind, folder in TARGETS:
    remote = {e.path: e.size for e in api.list_repo_tree(repo, repo_type=kind, recursive=True) if getattr(e, "size", None) is not None}
    local = {f.relative_to(folder).as_posix(): f.stat().st_size for f in folder.rglob("*") if f.is_file() and ".cache" not in f.parts}   # upload_large_folder keeps bookkeeping in .cache
    missing = [k for k in local if k not in remote]
    wrong = [k for k in local if k in remote and remote[k] != local[k] and not k.endswith(".md")]   # card text is rewritten by the hub
    print(f"verify {repo}: {len(local)} local files, {len(missing)} missing, {len(wrong)} size mismatches", flush=True)
    ok &= not missing and not wrong
print("RELEASE-VERIFIED" if ok else "RELEASE-PROBLEMS", flush=True)
sys.exit(0 if ok else 1)
