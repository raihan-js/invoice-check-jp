import json
import random

import pytest
from fastapi.testclient import TestClient

from invoicecheck import api
from invoicecheck.extraction import gold_to_target
from invoicecheck.registry import Registry
from invoicecheck.synth.invoice import make_invoice
from invoicecheck.synth.issuers import build_issuers, build_registry


@pytest.fixture()
def client():
    rng = random.Random(21)
    iss = build_issuers(rng, {"train": 6})
    recs = build_registry(rng, iss, 50)
    api._registry = Registry.from_records(recs)
    yield TestClient(api.app), rng, iss, recs
    api._registry = None


def test_health_reports_registry_size(client):
    c, *_ = client
    r = c.get("/health").json()
    assert r["status"] == "ok" and r["registry_size"] == 56 and "tax" in r["layers"]


def test_clean_invoice_is_approved_and_a_bad_number_goes_to_review(client):
    c, rng, iss, recs = client
    g = make_invoice(rng, 1, "train", iss[0], "株式会社受取", "h_classic__k0", recs)
    ok = c.post("/verify", json={"extraction": gold_to_target(g)}).json()
    assert ok["decision"] == "approve" and ok["reasons"] == []
    bad = gold_to_target(make_invoice(rng, 2, "train", iss[0], "株式会社受取", "h_classic__k0", recs, issue="reg_no_revoked"))
    r = c.post("/verify", json={"extraction": bad}).json()
    assert r["decision"] == "review" and "registry:revoked" in r["reasons"]


def test_layers_can_be_limited_and_garbage_is_reviewed_not_crashed(client):
    c, rng, iss, recs = client
    t = gold_to_target(make_invoice(rng, 3, "train", iss[1], "株式会社受取", "h_classic__k0", recs, issue="tax_total_wrong"))
    assert c.post("/verify", json={"extraction": t, "layers": ["schema", "check_digit"]}).json()["decision"] == "approve"
    assert c.post("/verify", json={"extraction": t}).json()["decision"] == "review"
    assert c.post("/verify", json={"extraction": {"foo": 1}}).json()["decision"] == "review"
    assert c.post("/verify", json={}).status_code == 422
