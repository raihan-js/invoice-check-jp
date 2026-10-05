"""Headline metrics of the verification layer for one system on one split.

For each cumulative layer set (none, schema, +check digit, +registry, +name, +tax = full):
  automation rate           share of invoices auto-approved (no human review needed)
  residual error (all)      share of ALL invoices that are approved yet contain a wrong extracted field
  residual error (approved) the same, among approved invoices only: how wrong is what gets through
  caught                    share of wrong extractions that the layers route to review
Invoices with an injected document issue (bad number, revoked issuer, wrong tax total) are scored separately: the right outcome is
review, whatever the extraction says. Clean invoices carry the extraction-error metrics.
"""
from .evaluation import bootstrap_ci
from .extraction import gold_to_target, score
from .verify import LAYERS, verify


def evaluate_verification(gold_rows, pred_by_id, registry):
    levels = [("none", [])] + [(LAYERS[n - 1] if n > 1 else "schema", LAYERS[:n]) for n in range(1, len(LAYERS) + 1)]
    out = {"n": len(gold_rows), "levels": {}}
    clean = [g for g in gold_rows if not g["document_issues"]]
    issue = [g for g in gold_rows if g["document_issues"]]
    out["n_clean"], out["n_issue"] = len(clean), len(issue)
    scored = {g["invoice_id"]: score(pred_by_id.get(g["invoice_id"]), gold_to_target(g)) for g in gold_rows}
    for name, layers in levels:
        appr_clean, resid_all, resid_appr, wrong_caught, issue_flagged = [], [], [], [], []
        for g in clean:
            p = pred_by_id.get(g["invoice_id"])
            approved = True if not layers else verify(p, registry, layers).approved
            exact = scored[g["invoice_id"]]["exact"]
            appr_clean.append(approved)
            resid_all.append(approved and not exact)
            if approved:
                resid_appr.append(not exact)
            if not exact:
                wrong_caught.append(not approved)
        for g in issue:
            p = pred_by_id.get(g["invoice_id"])
            issue_flagged.append(False if not layers else not verify(p, registry, layers).approved)
        out["levels"][name] = {
            "layers": layers, "automation_rate": bootstrap_ci(appr_clean), "residual_error_all": bootstrap_ci(resid_all),
            "residual_error_among_approved": bootstrap_ci(resid_appr), "wrong_extractions_caught": bootstrap_ci(wrong_caught),
            "document_issues_flagged": bootstrap_ci(issue_flagged),
        }
    # which check caught what (full rule), for wrong clean extractions and for issue documents
    from collections import Counter
    first_reason, issue_reason = Counter(), Counter()
    for g in clean:
        if not scored[g["invoice_id"]]["exact"]:
            v = verify(pred_by_id.get(g["invoice_id"]), registry)
            first_reason[v.reasons[0].split(":")[0] if v.reasons else "slipped_through"] += 1
    for g in issue:
        v = verify(pred_by_id.get(g["invoice_id"]), registry)
        issue_reason[(g["document_issues"][0], v.reasons[0].split(":")[0] if v.reasons else "missed")] += 1
    out["wrong_extractions_by_first_check"] = dict(first_reason)
    out["issue_documents_by_kind_and_check"] = {f"{k}->{c}": n for (k, c), n in sorted(issue_reason.items())}
    return out


def format_levels(summary):
    rows = ["| layers | automation | residual error (all) | residual among approved | wrong extractions caught | document issues flagged |", "|---|---|---|---|---|---|"]
    f = lambda c: "-" if c["mean"] is None else f"{100 * c['mean']:.1f}% [{100 * c['lo']:.1f}, {100 * c['hi']:.1f}]"
    for name, lv in summary["levels"].items():
        rows.append(f"| {name} | {f(lv['automation_rate'])} | {f(lv['residual_error_all'])} | {f(lv['residual_error_among_approved'])} | "
                    f"{f(lv['wrong_extractions_caught'])} | {f(lv['document_issues_flagged'])} |")
    return "\n".join(rows)
