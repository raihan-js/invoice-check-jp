# Invoice-Check JP

Japanese qualified-invoice (適格請求書) extraction where **no extracted field is trusted without a check**: registration numbers are verified by check digit and against the National Tax Agency registry, and per-rate tax is recomputed from the line items.

> Status: milestone 1 of 5 (registry and checkers) is done. Nothing below is a model result yet.

## Why

Since October 2023 a qualified invoice must carry a registration number (T + 13 digits), the amount per tax rate (10% standard, 8% reduced) and the tax for each rate. The registry of valid numbers is public, and the arithmetic is checkable, so a neural extractor can be audited by symbolic checks (the same pattern as [FedProc-Constrained](https://github.com/raihan-js/fedproc-constrained)). The headline will not be raw extraction accuracy but how many wrong extractions the checks catch, and how many slip through because they are valid but wrong.

## What exists (milestone 1)

| Module | What it does |
|---|---|
| `checkdigit.py` | Corporate-number (法人番号) check digit, registration-number parsing (`Ｔ－１０１０…` → `T1010…`) |
| `registry.py` | Local SQLite cache of the NTA corporate registry, validity on a date (active / expired / revoked), issuer-name matching |
| `tax.py` | Per-rate tax under 切り捨て / 四捨五入 / 切り上げ, line, subtotal and grand-total checks, with error codes |
| `normalize.py` | Era dates (令和 / 平成 / 昭和, R/H/S), full-width digits, yen formats, company-form variants |

24 tests (`pytest`), all passing.

## Measured so far (registry snapshot 2026-09-30)

- **Check digit validated on real data:** all 2,581,522 registered corporations pass (0 invalid): `results/registry_checkdigit.json`. 2.48 M active, 92.5 K expired, 10.2 K revoked.
- **What catches a corrupted registration number** (300,000 real numbers, one wrong digit, `results/error_anatomy.json`): the check digit catches 95.6%, the registry lookup 4.1%, and **0.29% land on a different real company**, so only an issuer-name comparison catches them. The check digit cannot see a `0↔9` substitution (its weighted sum is taken mod 9), and among the errors that survive it, 6.7% hit another registered company because registered numbers are clustered. For two adjacent digits swapped: 97.6% / 2.1% / 0.24%.

## Registry data and licence

Source: [国税庁適格請求書発行事業者公表サイト](https://www.invoice-kohyo.nta.go.jp/) monthly all-record download, corporations only (individuals' records are personal data and are not loaded). Used under the Public Data License 1.0 (公共データ利用規約 第1.0版). 出典：国税庁適格請求書発行事業者公表サイト（国税庁）を加工して作成. Cached locally, never republished; the site's search function is not scraped. Provenance (snapshot date, files, counts): `results/registry_provenance.json`.

## Plan

1. Registry and checkers (done)
2. Synthetic invoice generator, about 4,000 invoices from 20+ templates with gold JSON and a held-out set of unseen templates
3. Three systems: OCR + rules, Qwen2.5-VL-3B zero-shot, Qwen2.5-VL-3B QLoRA
4. Verification layer and routing: automation rate vs residual error rate
5. Release: FastAPI endpoint, HF dataset and adapter, write-up

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest
# registry: download the five h_all CSV zips from the NTA page (jinkakukbn=2, type=01), unzip into data/registry/csv, then
.venv/bin/python scripts/build_registry_db.py --snapshot 2026-09-30 --downloaded 2026-10-05
.venv/bin/python scripts/error_anatomy.py --n 300000
```

## Limitations

- Synthetic invoices (from milestone 2 on) are cleaner and more regular than real ones; an unseen-template hold-out is required and no claim extends to real invoices.
- Sole proprietors' numbers are not corporate numbers and have no public check-digit rule in this form; they can only be checked by registry lookup, and individuals' data is not loaded here.
- Tax rounding differs by issuer; the checker accepts all three conventions and reports which matched.
