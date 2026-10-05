import random

from invoicecheck.evaluation import bootstrap_ci, evaluate, summarise
from invoicecheck.extraction import gold_to_target
from invoicecheck.synth.invoice import make_invoice
from invoicecheck.synth.issuers import build_issuers, build_registry


def _gold(n=40):
    rng = random.Random(4)
    iss = build_issuers(rng, {"train": 6})
    reg = build_registry(rng, iss, 30)
    out = []
    for k in range(n):
        g = make_invoice(rng, k, "train", rng.choice(iss), "株式会社受取", "h_classic__k0" if k % 2 else "v_header__k1", reg)
        g["layout"] = "horizontal" if k % 2 else "vertical"
        out.append(g)
    return out


def test_perfect_predictions_score_100_and_missing_count_as_failures():
    gold = _gold()
    preds = [{"id": g["invoice_id"], "parsed": gold_to_target(g)} for g in gold]
    s = summarise(evaluate(gold, preds))
    assert s["exact"]["mean"] == 1.0 and s["parsed_json"] == len(gold)
    s2 = summarise(evaluate(gold, preds[:30]))
    assert s2["n"] == 40 and s2["predicted"] == 30 and abs(s2["exact"]["mean"] - 0.75) < 1e-9


def test_slices_and_ci_are_sane():
    gold = _gold()
    preds = []
    for g in gold:
        t = gold_to_target(g)
        if g["layout"] == "vertical":
            t["grand_total"] += 1                      # every vertical invoice wrong
        preds.append({"id": g["invoice_id"], "parsed": t})
    s = summarise(evaluate(gold, preds))
    assert s["exact_by_layout"]["horizontal"]["mean"] == 1.0 and s["exact_by_layout"]["vertical"]["mean"] == 0.0
    assert s["fields"]["grand_total"]["mean"] == 0.5 and s["fields"]["issuer_name"]["mean"] == 1.0
    ci = bootstrap_ci([1, 0] * 50)
    assert ci["lo"] < 0.5 < ci["hi"] and ci["n"] == 100


def test_bootstrap_is_seeded_and_empty_safe():
    assert bootstrap_ci([1, 0, 1, 1]) == bootstrap_ci([1, 0, 1, 1])
    assert bootstrap_ci([])["mean"] is None


def test_clopper_pearson_handles_zero_and_full_counts():
    from invoicecheck.evaluation import clopper_pearson
    lo, hi = clopper_pearson(0, 292)
    assert lo == 0.0 and 0.009 < hi < 0.014                 # about 3/n, the rule of three
    lo, hi = clopper_pearson(292, 292)
    assert hi == 1.0 and 0.986 < lo < 0.991
    lo, hi = clopper_pearson(50, 100)
    assert 0.39 < lo < 0.41 and 0.59 < hi < 0.61
    ci = bootstrap_ci([0] * 292)
    assert ci["k"] == 0 and ci["cp_hi"] > 0 and ci["lo"] == ci["hi"] == 0
