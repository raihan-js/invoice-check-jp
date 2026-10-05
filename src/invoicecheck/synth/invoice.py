"""Gold invoice generator: issuer, recipient, items, per-rate totals, printed date style, injected document issues.

The gold JSON is the label set for the extraction systems. `printed` holds the exact strings that appear on the page, so
a rendered page can be checked against its gold (render.py asserts every printed value is present in the page text).
"""
import random
from datetime import date, timedelta

from ..checkdigit import is_valid_registration_number
from ..tax import RATES, ROUNDINGS, check_invoice_tax, expected_tax, LineItem, RateTotal
from . import names

DATE_STYLES = ["reiwa_kanji", "reiwa_fullwidth", "reiwa_short", "western_slash", "western_kanji", "western_fullwidth"]
ISSUE_KINDS = ["reg_no_check_digit", "reg_no_unregistered", "reg_no_other_company", "reg_no_revoked", "tax_total_wrong"]
FW = str.maketrans("0123456789,", "０１２３４５６７８９，")


def fmt_date(iso, style):
    d = date.fromisoformat(iso)
    ry = d.year - 2018
    ry_s = "元" if ry == 1 else str(ry)
    if style == "reiwa_kanji":
        return f"令和{ry_s}年{d.month}月{d.day}日"
    if style == "reiwa_fullwidth":
        return f"令和{ry_s}年{d.month}月{d.day}日".translate(FW)
    if style == "reiwa_short":
        return f"R{ry}.{d.month}.{d.day}"
    if style == "western_slash":
        return f"{d.year}/{d.month:02d}/{d.day:02d}"
    if style == "western_kanji":
        return f"{d.year}年{d.month}月{d.day}日"
    return f"{d.year}年{d.month}月{d.day}日".translate(FW)


def yen(n, style):
    s = f"{n:,}"
    return {"yen_sign": f"¥{s}", "fullwidth": f"￥{s}".translate(FW), "en": f"{s}円", "plain": s}[style]


def make_invoice(rng, idx, split, issuer, recipient_name, template, registry_records, tax_included=None, issue=None):
    """One gold invoice. `registry_records` (list of Record) supplies decoys for 'other company' / 'revoked' issues."""
    n_items = rng.randint(2, 7)
    pool = rng.sample(names.PRODUCTS, k=min(n_items, len(names.PRODUCTS)))
    items = []
    for desc, (lo, hi), rate in pool:
        qty = rng.choice([1, 1, 2, 3, 5, 10, 12])
        price = rng.randrange(lo, hi + 1, 10 if hi > 1000 else 1)
        items.append({"description": desc, "quantity": qty, "unit_price": price, "amount": qty * price, "rate": rate})
    if tax_included is None:
        tax_included = rng.random() < 0.3
    sums = {}
    for it in items:
        sums[it["rate"]] = sums.get(it["rate"], 0) + it["amount"]
    totals = [{"rate": r, "subtotal": s, "tax": int(expected_tax(s, r, tax_included, issuer.rounding))} for r, s in sorted(sums.items(), reverse=True)]
    grand = sum(t["subtotal"] for t in totals) + (0 if tax_included else sum(t["tax"] for t in totals))
    first = max(date(2023, 10, 1), date.fromisoformat(issuer.registered))
    issue_date = (first + timedelta(days=rng.randint(0, (date(2026, 9, 30) - first).days))).isoformat()
    reg_no = issuer.reg_no
    issues = []
    if issue == "reg_no_check_digit":
        while True:      # the corruption must actually fail the check digit (a 0<->9 swap would not)
            pos = rng.randrange(1, 14)
            d = rng.choice([c for c in "0123456789" if c != reg_no[pos]])
            bad = reg_no[:pos] + d + reg_no[pos + 1:]
            if not is_valid_registration_number(bad):
                reg_no = bad
                break
        issues.append(issue)
    elif issue in ("reg_no_other_company", "reg_no_revoked", "reg_no_unregistered"):
        if issue == "reg_no_other_company":
            cand = [r for r in registry_records if r.process == "01" and r.reg_no != issuer.reg_no and r.registered <= issue_date]
            reg_no = rng.choice(cand).reg_no
        elif issue == "reg_no_revoked":
            cand = [r for r in registry_records if r.process == "04"]
            rec = rng.choice(cand)
            reg_no = rec.reg_no
            issue_date = (date.fromisoformat(rec.revoked) + timedelta(days=rng.randint(5, 200))).isoformat()
        else:  # a structurally valid number that no registry holds: unregistered issuer
            from .issuers import mint_numbers
            reg_no = mint_numbers(rng, 1, {r.reg_no for r in registry_records})[0]
        issues.append(issue)
    if issue == "tax_total_wrong":
        t = rng.choice(totals)
        ok_values = {int(expected_tax(t["subtotal"], t["rate"], tax_included, c)) for c in ROUNDINGS}
        while True:      # a wrong total that no rounding convention explains (a +/-1 yen change can look like another convention)
            bad = t["tax"] + rng.choice([-100, -10, -3, -2, -1, 1, 2, 3, 10, 100])
            if bad not in ok_values and bad >= 0:
                break
        t["tax"] = bad
        grand = sum(x["subtotal"] for x in totals) + (0 if tax_included else sum(x["tax"] for x in totals))
        issues.append(issue)
    style = rng.choice(DATE_STYLES)
    gold = {
        "invoice_id": f"inv_{idx:06d}", "split": split, "template": template,
        "issuer": {"name": issuer.name, "registration_number": reg_no, "address": issuer.address, "phone": issuer.phone},
        "true_issuer_registration_number": issuer.reg_no,
        "recipient": {"name": recipient_name},
        "invoice_number": f"{rng.choice(['INV', 'No.', 'R'])}-{rng.randint(1000, 99999)}",
        "issue_date": issue_date, "date_style": style, "tax_included": tax_included, "rounding": issuer.rounding,
        "items": items, "totals": totals, "grand_total": grand, "seal": issuer.seal, "document_issues": issues,
        "yen_style": rng.choice(["yen_sign", "fullwidth", "en", "plain"]),
        "seal_overlap": bool(issuer.seal and rng.random() < 0.25),
    }
    gold["printed"] = {"issue_date": fmt_date(issue_date, style)}
    return gold


def tax_check(gold):
    """Run the arithmetic checker on a gold invoice (used by tests and by the verification layer)."""
    items = [LineItem(i["description"], i["quantity"], i["unit_price"], i["amount"], i["rate"]) for i in gold["items"]]
    totals = [RateTotal(t["rate"], t["subtotal"], t["tax"]) for t in gold["totals"]]
    return check_invoice_tax(items, totals, gold["grand_total"], gold["tax_included"])
