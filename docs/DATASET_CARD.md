---
license: cc-by-4.0
language: [ja]
task_categories: [image-to-text, document-question-answering]
tags: [invoice, japanese, document-ai, synthetic, verification, qualified-invoice]
size_categories: [1K<n<10K]
---

# Invoice-Check JP (synthetic)

4,100 **synthetic** Japanese qualified invoices (適格請求書) as images with gold JSON labels, plus the synthetic registry the invoices can be verified against. Built to measure how many wrong extractions symbolic checks (check digit, registry lookup, issuer-name match, tax arithmetic) catch, and how many slip through. Code and results: https://github.com/raihan-js/invoice-check-jp

## What is real and what is not

- **Every company, address, phone number, bank detail and recipient is fictitious.** Names are composed from parts; none appears in the NTA registry snapshot of 2026-09-30 (checked, collisions rejected).
- **Registration numbers are minted:** 12 random digits plus the real corporate-number check digit (so they are structurally valid), rejected if they exist in the real registry. They are not registered to anyone.
- **The registry in this dataset is synthetic** (`registry_synthetic.jsonl`, same fields as the NTA data: number, name, address, process 01 active / 03 expired / 04 revoked, dates). No NTA data is included or redistributed. The real registry (Public Data License 1.0, 出典：国税庁適格請求書発行事業者公表サイト) was used only to reject collisions and to measure how corrupted numbers behave (a separate analysis in the code repository).
- Do not use these images as, or to imitate, real invoices.

## Contents

| split | invoices | templates | notes |
|---|---|---|---|
| train | 3,000 | 20 (4 layouts x 5 skins) | for fine-tuning |
| val | 300 | same 20 | prompt and checkpoint selection |
| test | 600 | same 20 | issuers disjoint from train and val |
| holdout | 200 | 4 never seen in training (2 new layouts x 2 skins, one fully vertical) | layout generalisation |

Issuers are disjoint across splits, so a model cannot succeed by memorising number-name pairs. About 12% of invoices carry one injected document issue (`document_issues`): a registration number with a bad check digit, an unregistered number, a revoked issuer, another company's number, or a wrong tax total.

Per invoice (`gold_<split>.jsonl`): `image`, `template`, `layout` (horizontal / vertical), `issuer` (name, registration_number, address, phone), `recipient`, `invoice_number`, `issue_date` (ISO) and the printed `date_style` (令和 kanji, full-width, R7.3.14, Western slash / kanji / full-width), `tax_included`, `rounding` (切り捨て / 四捨五入 / 切り上げ, fixed per issuer), `items` (description, quantity, unit_price, amount, rate 10 or 8; reduced-rate items carry ※), `totals` (subtotal and tax per rate), `grand_total`, `seal` / `seal_overlap` (角印, 1 in 4 stamps lands on the address and registration lines), `yen_style`, `document_issues`.

Images are A4 at 96 dpi x 1.25 (about 992 x 1404), rendered from HTML with Noto Sans / Serif CJK JP, then degraded like a scan: small rotation, blur, grain, fold lines, edge shadow, JPEG (70% of images).

## Integrity checks

Every page was checked after rendering: each gold value (names, number, date, amounts) is present in the page text, content fits on the page, and the tax arithmetic of every clean invoice passes (3,611 of 3,611). Regeneration with the same seed reproduces the labels exactly.

## Limitations

Synthetic invoices are cleaner and more regular than real ones: 6 layouts, a catalogue of 18 products, two tax rates, corporations only (no sole proprietors, whose numbers are not corporate numbers and have no public check-digit rule). Results on this dataset do not transfer to real invoices without evidence from real documents.

## Generation

`python scripts/generate_invoices.py --train 3000 --val 300 --test 600 --holdout 200 --seed 0` (code repository). License: CC BY 4.0 for the images, labels and synthetic registry.
