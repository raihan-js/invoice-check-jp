# AGENTS.md — invoice-check-jp

Wave-two project 1 (spec: `../ideas-v2.json`, id `invoice-check-jp`). Japanese qualified-invoice extraction verified against the NTA registry, check digits and tax arithmetic. Targets: Money Forward, PayPay Card, Treasure AI, LegalOn, Citadel AI.

## Rules
- Registry data: corporations only, local cache, never committed or republished (`data/` is git-ignored); keep attribution and provenance (`results/registry_provenance.json`). Never download or load individuals' records.
- Synthetic invoices must carry fictitious issuers: mint valid-check-digit numbers and reject any that exist in the real registry, so no synthetic invoice carries a real company's name or number.
- Every number in README/articles comes from `results/` and carries its scope. Rule-based scorers only. Follow `../noeon-prep/content/interview/09-never-say.md`.
- Headline metric: residual error rate after verification vs automation rate, with 95% CIs; always report the unseen-template hold-out separately.

## Status
- M1 registry and checkers: DONE (24 tests). Check digit valid for 2,581,522/2,581,522 registered corporations; error anatomy in `results/error_anatomy.json`.
- Next: M2 synthetic invoice generator (HTML templates rendered with headless Chrome, Noto CJK fonts installed).

## Commands
`python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest`
