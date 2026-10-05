# AGENTS.md — invoice-check-jp

Wave-two project 1 (spec: `../ideas-v2.json`, id `invoice-check-jp`). Japanese qualified-invoice extraction verified against the NTA registry, check digits and tax arithmetic. Targets: Money Forward, PayPay Card, Treasure AI, LegalOn, Citadel AI.

## Rules
- Registry data: corporations only, local cache, never committed or republished (`data/` is git-ignored); keep attribution and provenance (`results/registry_provenance.json`). Never download or load individuals' records.
- Synthetic invoices must carry fictitious issuers: mint valid-check-digit numbers and reject any that exist in the real registry, so no synthetic invoice carries a real company's name or number.
- Every number in README/articles comes from `results/` and carries its scope. Rule-based scorers only. Follow `../noeon-prep/content/interview/09-never-say.md`.
- Headline metric: residual error rate after verification vs automation rate, with 95% CIs; always report the unseen-template hold-out separately.

## Status (2026-10-06)
- M1-M4 DONE, M5 staged locally (not published): 69 tests; 4,100-invoice dataset (seed 0); three systems scored on test and hold-out; verification layer + API; README, article (`devto_article.md`), Japanese Zenn summary (`zenn_summary_ja.md`), dataset card (`docs/DATASET_CARD.md`), release packages (`python scripts/build_release.py` -> `data/release/{dataset,adapter}`).
- Results (test, 600): OCR+rules 37.8% exact, zero-shot 5.3%, QLoRA 83.0% [80.0, 85.8]; hold-out QLoRA 51.5% (unseen horizontal 99%, unseen fully vertical 4%). Full check rule on QLoRA: 86.8% auto-approved, 0/461 approved with a wrong covered field; documents with injected issues 69/69 routed to review. Everything in `results/REPORT.md`.
- Published 2026-10-06: HF dataset `raihan-js/invoice-check-jp` and adapter `raihan-js/invoice-check-jp-qwen2.5-vl-3b-lora` (verified, public). Resume updated. Portfolio card committed locally, not pushed. Article queued with ready=false.
- BLOCKED: the permission classifier refused `gh repo create raihan-js/invoice-check-jp --public ...`; the owner must run it (`--source=. --remote=origin --push`). Only then: push the portfolio repo, set the queue entry ready, clear the project. Adapter licence is non-commercial (Qwen Research License): say so wherever it is described.
- Defined before the fine-tuned model was scored: covered fields (registration number, issuer, tax basis, totals, grand total, item numbers) vs uncovered (recipient, invoice number, date, item text). Never tune on test or hold-out.

## Commands
`python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest`
