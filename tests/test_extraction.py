import copy
import random

from invoicecheck.extraction import FIELDS, gold_to_target, normalize_prediction, parse_model_json, score
from invoicecheck.synth.invoice import make_invoice
from invoicecheck.synth.issuers import build_issuers, build_registry


def _gold():
    rng = random.Random(2)
    iss = build_issuers(rng, {"train": 4})
    return make_invoice(rng, 1, "train", iss[0], "株式会社受取", "h_classic__k0", build_registry(rng, iss, 20))


def test_perfect_prediction_is_exact():
    t = gold_to_target(_gold())
    r = score(copy.deepcopy(t), t)
    assert r["exact"] and all(r["fields"].values()) and r["items_correct"] == r["items_total"]


def test_surface_variants_normalise_to_the_same_answer():
    t = gold_to_target(_gold())
    p = copy.deepcopy(t)
    p["registration_number"] = "Ｔ" + t["registration_number"][1:].translate(str.maketrans("0123456789", "０１２３４５６７８９"))
    p["issuer_name"] = " " + t["issuer_name"].replace("株式会社", "(株)") + " "
    p["issue_date"] = "令和" + str(int(t["issue_date"][:4]) - 2018) + "年" + str(int(t["issue_date"][5:7])) + "月" + str(int(t["issue_date"][8:])) + "日"
    p["grand_total"] = "￥" + f"{t['grand_total']:,}"
    p["items"][0]["quantity"] = str(t["items"][0]["quantity"])
    assert score(p, t)["exact"]


def test_each_error_breaks_exactly_its_field():
    t = gold_to_target(_gold())
    for field, change in [("registration_number", lambda v: v[:-1] + ("1" if v[-1] != "1" else "2")), ("grand_total", lambda v: v + 1),
                          ("issue_date", lambda v: "2020-01-01"), ("recipient_name", lambda v: v + "X"), ("tax_included", lambda v: not v)]:
        p = copy.deepcopy(t)
        p[field] = change(p[field])
        r = score(p, t)
        assert not r["exact"] and [f for f, ok in r["fields"].items() if not ok] == [field], field


def test_items_and_totals_are_whole_list_matches():
    t = gold_to_target(_gold())
    p = copy.deepcopy(t)
    p["items"][-1]["amount"] += 1
    r = score(p, t)
    assert not r["fields"]["items"] and r["items_correct"] == r["items_total"] - 1 and r["fields"]["totals"]
    p = copy.deepcopy(t)
    p["totals"] = p["totals"] + [{"rate": 8, "subtotal": 1, "tax": 0}]
    assert not score(p, t)["fields"]["totals"]
    p = copy.deepcopy(t)
    p["items"] = p["items"][:-1]
    assert not score(p, t)["fields"]["items"]


def test_garbage_prediction_scores_zero_without_crashing():
    t = gold_to_target(_gold())
    for bad in (None, {}, "text", {"items": "x", "totals": [1, 2]}, {"grand_total": [1]}):
        r = score(bad, t)
        assert not r["exact"] and r["items_correct"] == 0


def test_parse_model_json_variants():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_model_json('Here is the result: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    assert parse_model_json("no json here") is None and parse_model_json('{"a": ') is None and parse_model_json(None) is None


def test_fields_list_is_stable():
    assert FIELDS == ["issuer_name", "registration_number", "issue_date", "recipient_name", "invoice_number", "tax_included", "grand_total", "items", "totals"]
    assert set(normalize_prediction({}).keys()) == set(FIELDS)
