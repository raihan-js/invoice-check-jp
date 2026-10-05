"""Per-rate tax arithmetic for qualified invoices.

Japanese qualified invoices show, for each applicable rate (10% standard, 8% reduced), the amount subject to that rate
and the tax on it. Tax is rounded once per invoice per rate, and the issuer chooses the convention: 切り捨て (floor),
四捨五入 (round half up) or 切り上げ (ceil). The checker therefore accepts any convention and records which matched; a
mismatch under all three is a real discrepancy.

    tax-excluded amounts:  tax = round(subtotal * rate / 100)
    tax-included amounts:  tax = round(subtotal * rate / (100 + rate))

Exact rational arithmetic (fractions) avoids float errors on half-yen cases.
"""
import math
from dataclasses import dataclass, field
from fractions import Fraction

RATES = (10, 8)
ROUNDINGS = {
    "floor": lambda x: math.floor(x),
    "half_up": lambda x: math.floor(x + Fraction(1, 2)),
    "ceil": lambda x: math.ceil(x),
}


@dataclass
class LineItem:
    description: str
    quantity: int
    unit_price: int
    amount: int          # line amount as printed
    rate: int            # 10 or 8 (8 = the item carries the reduced-rate marker ※)


@dataclass
class RateTotal:
    rate: int
    subtotal: int        # amount subject to this rate, as printed
    tax: int             # tax for this rate, as printed


@dataclass
class TaxResult:
    ok: bool
    errors: list = field(default_factory=list)       # codes, see below
    matched: dict = field(default_factory=dict)      # rate -> list of conventions whose tax equals the printed tax
    convention: list = field(default_factory=list)   # conventions that explain every rate at once (may be empty)


def expected_tax(subtotal, rate, tax_included, rounding):
    """Tax for `subtotal` at `rate` percent under one rounding convention (an int)."""
    base = Fraction(subtotal * rate, 100 + rate) if tax_included else Fraction(subtotal * rate, 100)
    return ROUNDINGS[rounding](base)


def check_invoice_tax(items, totals, grand_total, tax_included):
    """Check line amounts, per-rate subtotals, per-rate tax and the grand total.

    Error codes: line_amount_mismatch, unknown_rate, subtotal_mismatch, rate_missing, tax_mismatch, total_mismatch.
    """
    errors = []
    sums = {}
    for it in items:
        if it.rate not in RATES:
            errors.append("unknown_rate")
            continue
        if it.quantity * it.unit_price != it.amount:
            errors.append("line_amount_mismatch")
        sums[it.rate] = sums.get(it.rate, 0) + it.amount
    stated = {t.rate: t for t in totals}
    for rate, s in sums.items():
        if rate not in stated:
            errors.append("rate_missing")
        elif stated[rate].subtotal != s:
            errors.append("subtotal_mismatch")
    matched = {}
    for rate, t in stated.items():
        matched[rate] = [name for name in ROUNDINGS if expected_tax(t.subtotal, rate, tax_included, name) == t.tax]
        if not matched[rate]:
            errors.append("tax_mismatch")
    convention = [n for n in ROUNDINGS if stated and all(n in matched[r] for r in matched)]
    subtotal_sum = sum(t.subtotal for t in totals)
    tax_sum = sum(t.tax for t in totals)
    expected_total = subtotal_sum if tax_included else subtotal_sum + tax_sum
    if grand_total != expected_total:
        errors.append("total_mismatch")
    return TaxResult(ok=not errors, errors=sorted(set(errors)), matched=matched, convention=convention)
