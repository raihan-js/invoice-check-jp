"""Verification layer: symbolic checks on an extracted invoice, and a routing decision.

An extraction is never trusted on its own. It is checked in layers (each layer adds checks; the full rule is every layer):

  schema       the required fields are present and well-typed
  check_digit  the registration number is T + 13 digits with a valid corporate-number check digit
  registry     the number is registered, and active on the invoice date (not revoked, expired or not yet registered)
  name         the printed issuer name matches the registry name for that number (exact or same name without the legal form)
  tax          line amounts, per-rate subtotals, per-rate tax (any rounding convention) and the grand total are consistent

Auto-approve only when every enabled check passes; anything else goes to human review, with the failed check codes as reasons.
"""
import re
from dataclasses import dataclass, field

from .checkdigit import is_valid_registration_number, normalize_registration_number
from .normalize import parse_date
from .registry import name_match
from .tax import LineItem, RateTotal, check_invoice_tax

LAYERS = ["schema", "check_digit", "registry", "name", "tax"]
DATE_MIN, DATE_MAX = "2023-10-01", "2026-12-31"      # qualified invoices exist from 2023-10-01


@dataclass
class Verdict:
    approved: bool
    reasons: list = field(default_factory=list)       # failed check codes
    detail: dict = field(default_factory=dict)


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def check_schema(p):
    errs = []
    if not isinstance(p, dict) or not p:
        return ["schema:not_an_object"]
    for k in ("issuer_name", "registration_number", "issue_date", "recipient_name"):
        if not isinstance(p.get(k), str) or not p.get(k).strip():
            errs.append(f"schema:{k}_missing")
    if not isinstance(p.get("tax_included"), bool):
        errs.append("schema:tax_included_missing")
    if _int(p.get("grand_total")) is None:
        errs.append("schema:grand_total_missing")
    items, totals = p.get("items"), p.get("totals")
    if not isinstance(items, list) or not items:
        errs.append("schema:items_missing")
    elif not all(isinstance(i, dict) and all(_int(i.get(k)) is not None for k in ("quantity", "unit_price", "amount", "rate")) and isinstance(i.get("description"), str) for i in items):
        errs.append("schema:item_malformed")
    if not isinstance(totals, list) or not totals:
        errs.append("schema:totals_missing")
    elif not all(isinstance(t, dict) and all(_int(t.get(k)) is not None for k in ("rate", "subtotal", "tax")) for t in totals):
        errs.append("schema:total_malformed")
    d = parse_date(str(p.get("issue_date", ""))) if p.get("issue_date") else None
    if p.get("issue_date") and (d is None or not (DATE_MIN <= d <= DATE_MAX)):
        errs.append("schema:date_invalid")
    return errs


def verify(pred, registry, layers=LAYERS):
    """Run the enabled layers; returns a Verdict. `registry` is a Registry (real snapshot or the synthetic one)."""
    reasons, detail = [], {}
    schema_errs = check_schema(pred)
    if "schema" in layers:
        reasons += schema_errs
    if schema_errs and any(e.endswith("_missing") or e.endswith("not_an_object") for e in schema_errs):
        return Verdict(not reasons, reasons, detail) if "schema" not in layers else Verdict(False, reasons, detail)
    reg = normalize_registration_number(pred.get("registration_number"))
    iso = parse_date(str(pred.get("issue_date", "")))
    if "check_digit" in layers and not (reg and is_valid_registration_number(reg)):
        reasons.append("check_digit:invalid")
    if reg and ("registry" in layers or "name" in layers):
        status = registry.status(reg, iso) if iso else "not_found"
        detail["registry_status"] = status
        if "registry" in layers and status != "valid":
            reasons.append(f"registry:{status}")
        if "name" in layers:
            rec = registry.lookup(reg)
            m = name_match(pred.get("issuer_name", ""), rec.name) if rec else "no_record"
            detail["name_match"] = m
            if m not in ("exact", "same_core"):
                reasons.append(f"name:{m}")
    elif ("registry" in layers or "name" in layers) and not reg:
        reasons.append("registry:no_number")
    if "tax" in layers and not schema_errs:
        res = check_invoice_tax([LineItem(i["description"], i["quantity"], i["unit_price"], i["amount"], i["rate"]) for i in pred["items"]],
                                [RateTotal(t["rate"], t["subtotal"], t["tax"]) for t in pred["totals"]], pred["grand_total"], pred["tax_included"])
        detail["tax_convention"] = res.convention
        reasons += [f"tax:{e}" for e in res.errors]
    return Verdict(not reasons, reasons, detail)
