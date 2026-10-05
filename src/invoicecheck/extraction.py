"""Extraction schema, gold -> target conversion, prediction normalisation and scoring (rule-based, no LLM judge).

Fields: issuer_name, registration_number, issue_date (ISO), recipient_name, invoice_number, tax_included, items (ordered list of
description / quantity / unit_price / amount / rate), totals (per rate: subtotal, tax) and grand_total. A field is correct
if its normalised value equals the normalised gold value. Items and totals must match as whole ordered lists; item-level
accuracy is also reported over gold items (aligned by position). An invoice is correct only if every field is correct.
"""
import json
import re

from .checkdigit import normalize_registration_number
from .normalize import nfkc, normalize_name, parse_date, to_int_yen

SCALAR_FIELDS = ["issuer_name", "registration_number", "issue_date", "recipient_name", "invoice_number", "tax_included", "grand_total"]
FIELDS = SCALAR_FIELDS + ["items", "totals"]
ITEM_KEYS = ["description", "quantity", "unit_price", "amount", "rate"]

SCHEMA_TEXT = """{
  "issuer_name": str, "registration_number": "T" + 13 digits, "issue_date": "YYYY-MM-DD", "recipient_name": str,
  "invoice_number": str, "tax_included": bool (amounts include tax),
  "items": [{"description": str, "quantity": int, "unit_price": int, "amount": int, "rate": 10 or 8}],
  "totals": [{"rate": 10 or 8, "subtotal": int, "tax": int}], "grand_total": int
}"""


def gold_to_target(g):
    return {
        "issuer_name": g["issuer"]["name"], "registration_number": g["issuer"]["registration_number"], "issue_date": g["issue_date"],
        "recipient_name": g["recipient"]["name"], "invoice_number": g["invoice_number"], "tax_included": g["tax_included"],
        "items": [{k: it[k] for k in ITEM_KEYS} for it in g["items"]],
        "totals": [{"rate": t["rate"], "subtotal": t["subtotal"], "tax": t["tax"]} for t in g["totals"]],
        "grand_total": g["grand_total"],
    }


def parse_model_json(text):
    """First JSON object in a model's output (tolerates code fences and prose around it); None if there is none."""
    if text is None:
        return None
    s = re.sub(r"```(?:json)?", "", text)
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        depth += (s[i] == "{") - (s[i] == "}")
        if depth == 0:
            try:
                return json.loads(s[start:i + 1])
            except json.JSONDecodeError:
                return None
    return None


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    return to_int_yen(v) if v is not None else None


def _bool(v):
    if isinstance(v, bool):
        return v
    return {"true": True, "false": False}.get(str(v).strip().lower())


def normalize_prediction(p):
    """Canonical comparable form of a prediction (or a target): the same function is applied to both sides."""
    p = p if isinstance(p, dict) else {}
    items = []
    for it in p.get("items") or []:
        it = it if isinstance(it, dict) else {}
        items.append((normalize_name(it.get("description", "")), _int(it.get("quantity")), _int(it.get("unit_price")),
                      _int(it.get("amount")), _int(it.get("rate"))))
    totals = []
    for t in p.get("totals") or []:
        t = t if isinstance(t, dict) else {}
        totals.append((_int(t.get("rate")), _int(t.get("subtotal")), _int(t.get("tax"))))
    date = p.get("issue_date")
    return {
        "issuer_name": normalize_name(p.get("issuer_name", "")),
        "registration_number": normalize_registration_number(p.get("registration_number")) or nfkc(p.get("registration_number", "")),
        "issue_date": parse_date(str(date)) or nfkc(date or "") if date else "",
        "recipient_name": normalize_name(p.get("recipient_name", "")),
        "invoice_number": re.sub(r"\s+", "", nfkc(p.get("invoice_number", ""))),
        "tax_included": _bool(p.get("tax_included")),
        "grand_total": _int(p.get("grand_total")),
        "items": items, "totals": totals,
    }


def score(pred, target):
    """Per-field correctness, item-level accuracy and whole-invoice exact match for one invoice."""
    a, b = normalize_prediction(pred), normalize_prediction(target)
    ok = {f: a[f] == b[f] for f in FIELDS}
    n_gold = len(b["items"])
    item_hits = sum(1 for i, g_it in enumerate(b["items"]) if i < len(a["items"]) and a["items"][i] == g_it)
    return {"fields": ok, "exact": all(ok.values()), "items_correct": item_hits, "items_total": n_gold, "parsed": isinstance(pred, dict) and bool(pred)}
