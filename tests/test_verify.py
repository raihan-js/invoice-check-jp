import copy
import random

import pytest

from invoicecheck.extraction import gold_to_target
from invoicecheck.registry import Registry
from invoicecheck.synth.invoice import ISSUE_KINDS, make_invoice
from invoicecheck.synth.issuers import build_issuers, build_registry
from invoicecheck.verify import LAYERS, check_schema, verify


@pytest.fixture(scope="module")
def world():
    rng = random.Random(11)
    iss = build_issuers(rng, {"train": 10})
    recs = build_registry(rng, iss, 200)
    return rng, iss, recs, Registry.from_records(recs)


def test_clean_invoices_are_approved_at_every_layer(world):
    rng, iss, recs, reg = world
    for k in range(150):
        t = gold_to_target(make_invoice(rng, k, "train", rng.choice(iss), "株式会社受取", "h_classic__k0", recs))
        v = verify(t, reg)
        assert v.approved and v.reasons == [], v.reasons
        for n in range(1, len(LAYERS) + 1):
            assert verify(t, reg, LAYERS[:n]).approved


@pytest.mark.parametrize("kind,expected", [("reg_no_check_digit", "check_digit:invalid"), ("reg_no_unregistered", "registry:not_found"),
                                           ("reg_no_revoked", "registry:revoked"), ("reg_no_other_company", "name:different"), ("tax_total_wrong", "tax:tax_mismatch")])
def test_document_issues_are_routed_to_review_by_the_right_check(world, kind, expected):
    rng, iss, recs, reg = world
    for k in range(40):
        g = make_invoice(rng, k, "train", rng.choice(iss), "株式会社受取", "h_classic__k0", recs, issue=kind)
        v = verify(gold_to_target(g), reg)
        assert not v.approved and expected in v.reasons, (kind, v.reasons)


def test_each_extraction_error_is_caught_or_known_to_slip_through(world):
    rng, iss, recs, reg = world
    g = make_invoice(rng, 1, "train", iss[0], "株式会社受取", "h_classic__k0", recs)
    t = gold_to_target(g)
    # caught: wrong amount (arithmetic), wrong issuer name (name check), wrong digit (check digit), wrong date (registry window)
    bad = copy.deepcopy(t); bad["items"][0]["amount"] += 1
    assert not verify(bad, reg).approved
    bad = copy.deepcopy(t); bad["issuer_name"] = "株式会社別会社"
    assert verify(bad, reg).reasons == ["name:different"]
    bad = copy.deepcopy(t); bad["registration_number"] = t["registration_number"][:-1] + ("1" if t["registration_number"][-1] != "1" else "2")
    assert "check_digit:invalid" in verify(bad, reg).reasons
    # slips through: an error in a field no check can see (recipient, invoice number) is approved: residual error by design
    bad = copy.deepcopy(t); bad["recipient_name"] = "株式会社別の宛先"
    assert verify(bad, reg).approved
    bad = copy.deepcopy(t); bad["invoice_number"] = "INV-0"
    assert verify(bad, reg).approved


def test_schema_failures_never_crash_and_are_never_approved(world):
    _, _, _, reg = world
    for p in (None, {}, "x", {"items": "a"}, {"issuer_name": "a", "registration_number": 5}):
        assert not verify(p, reg).approved
    assert "schema:not_an_object" in check_schema(None)


def test_layers_are_cumulative(world):
    rng, iss, recs, reg = world
    g = make_invoice(rng, 3, "train", iss[1], "株式会社受取", "h_classic__k0", recs, issue="reg_no_unregistered")
    t = gold_to_target(g)
    assert verify(t, reg, ["schema", "check_digit"]).approved                  # valid digits, fine until the registry is consulted
    assert not verify(t, reg, ["schema", "check_digit", "registry"]).approved
