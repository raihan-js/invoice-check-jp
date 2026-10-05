"""Gold alignment: every value the gold says is printed must be present in the rendered page text (and fit on the page)."""
import re
import unicodedata

from .invoice import yen


def _n(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s)))


def printed_values(g):
    """The exact strings that must appear on the page for this gold invoice."""
    ys = g["yen_style"]
    vals = [g["issuer"]["name"], g["issuer"]["registration_number"], g["issuer"]["address"], g["recipient"]["name"],
            g["invoice_number"], g["printed"]["issue_date"], yen(g["grand_total"], ys)]
    for it in g["items"]:
        vals += [it["description"], str(it["quantity"]), yen(it["unit_price"], ys), yen(it["amount"], ys)]
    for t in g["totals"]:
        vals += [f'{t["rate"]}%', yen(t["subtotal"], ys), yen(t["tax"], ys)]
    return vals


def missing_values(g, page_text):
    text = _n(page_text)
    return [v for v in printed_values(g) if _n(v) not in text]
