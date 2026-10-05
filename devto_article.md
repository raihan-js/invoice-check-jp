# Invoice-Check JP: A 3B Model Reads the Invoice, Checks Decide Whether to Trust It

*A QLoRA-tuned vision-language model extracts Japanese qualified invoices; a check digit, a registry lookup and tax arithmetic decide what gets automated. On synthetic invoices: 86.8% auto-approved, and none of the approved invoices had a wrong field those checks can catch.*

---

![Invoice-Check JP results](https://raw.githubusercontent.com/raihan-js/invoice-check-jp/HEAD/images/invoice-check-jp.png)

> Scope note: everything here is measured on **synthetic invoices** with fictitious companies (600 test invoices, 200 hold-out invoices on layouts never seen in training), one model, one training run. It says nothing yet about real invoices.

## The problem

Since October 2023 a Japanese qualified invoice (適格請求書) must show a registration number (T plus 13 digits), the amount per tax rate (10% standard, 8% reduced) and the tax for each rate. That gives an extractor something unusual: **symbolic ground truth to check itself against.** The registry of valid numbers is public, a corporate number carries a check digit, and the tax is arithmetic. So the question I care about is not "how accurate is the model" but "how many wrong extractions do the checks catch, and how many slip through?"

## What I built

Three extractors that emit the same JSON: hand-written rules on PaddleOCR text boxes, Qwen2.5-VL-3B-Instruct zero-shot, and the same model with a QLoRA adapter trained on 3,000 synthetic invoices (one epoch, 4 h 57 min on an RTX 3060). Then five cumulative checks: schema, check digit, registry (registered, and active on the invoice date), issuer-name match against the registry, and tax arithmetic under all three rounding conventions (切り捨て, 四捨五入, 切り上げ). If every check passes the invoice is auto-approved; otherwise it goes to a human with the failed checks as reasons.

## The data, and three bugs my tests found

I did not want fake invoices carrying real companies' names, so every issuer is fictitious: names composed from parts, registration numbers minted with the real check digit, and anything that exists in the NTA registry snapshot rejected. The registry the checks run against ships with the dataset and is synthetic too. 4,100 invoices from 6 layouts (including vertical 縦書き), stamps (角印), 令和 and Western dates, full-width digits, scan noise. Every rendered page is checked against its gold labels, and issuers are disjoint across splits.

The tests earned their keep. They found that (1) about one in five of my "clean" invoices was dated before its issuer registered, so the verifier rightly called them invalid; (2) a one-yen error injected into a tax total can look exactly like a different rounding convention, so it is genuinely undetectable and must be excluded from "injected errors"; (3) my "corrupt one digit" generator sometimes swapped a 0 and a 9, which the check digit cannot see because its weighted sum is taken mod 9.

## Results

| Test split (600) | Whole invoice exact | Auto-approved (full rule) | Wrong *covered* field among approved |
|---|---|---|---|
| OCR + rules | 37.8% [33.8, 41.7] | 55.0% | 0 of 292 (95% upper bound 1.3%) |
| Zero-shot | 5.3% [3.7, 7.2] | 8.1% | 3 of 43 (7.0%) |
| QLoRA | **83.0% [80.0, 85.8]** | **86.8% [83.6, 89.6]** | **0 of 461 (upper bound 0.8%)** |

"Covered" means a check can catch an error in the field: registration number, issuer name, tax basis, totals and the numbers in the items. I fixed that definition before scoring the fine-tuned model. Without the checks, 12.8% of the fine-tuned model's invoices have a wrong covered field. The injected document problems (a bad check digit, an unregistered number, a revoked issuer, another company's number, a wrong tax total) were routed to review 69 times out of 69, and 95.7% were caught by the check meant for them.

## What the checks cannot see

Of the fine-tuned model's approved invoices, 4.6% still contain an error, all in fields nothing verifies: ten wrong invoice numbers, ten wrong dates, one item. The registry knows who the issuer is, not who the customer is, and a wrong date inside the issuer's valid window passes. For the OCR baseline it is worse: 32% of approved invoices carry a typo in an item description (費 read as 费) that no arithmetic can detect. The checks make the covered fields safe to automate; the rest needs another control.

## Where it fails

Horizontal layouts: 97.3% exact on test, and 99.0% on a horizontal layout the model never saw. Vertical layouts are the weak spot: 40.0% on test, driven by Latin text printed sideways (registration number 62.7%, date 82.7%) while tables are fine, and 4% on an unseen fully vertical layout whose table is rotated. The learning curve says more of the same data will not fix it: 8.7% exact with zero training invoices, 84.7% with 800, 89.3% with 2,400 and with 3,000.

## A number the synthetic registry hides

On the real registry (2.58 million corporations, all of which pass the check digit), I corrupted one digit of 300,000 registered numbers: the check digit catches 95.6%, the lookup 4.1%, and **0.29% land on a different real company**, because registered numbers are clustered. Only comparing the issuer name catches those. My synthetic registry is not clustered, so it understates this; the name check is the safety net.

## Limitations

- Synthetic invoices are cleaner and more regular than real ones: 6 layouts, 18 products, two tax rates, corporations only. No claim extends to real invoices.
- Sole proprietors are not covered (no public check-digit rule; individuals' registry data is personal data and is not loaded).
- One model, one run, one seed.
- The base model, Qwen2.5-VL-3B-Instruct, is under the Qwen Research License, so the adapter is non-commercial research only.

## Reproduce

Code, tests (69), dataset generator and every result file are in the repository; the dataset and adapter are on Hugging Face. `bash scripts/gpu_chain.sh` reruns zero-shot, training and the fine-tuned evaluation, resuming after a crash.

## What's next

A test on real invoices I have the right to use; a check for the recipient from a customer master; a larger base model with a permissive licence; vertical layouts with more than one training structure.

---

*Repo: github.com/raihan-js/invoice-check-jp · Data: huggingface.co/datasets/raihan-js/invoice-check-jp · Adapter: huggingface.co/raihan-js/invoice-check-jp-qwen2.5-vl-3b-lora. Registry data: 出典：国税庁適格請求書発行事業者公表サイト（国税庁）を加工して作成.*
