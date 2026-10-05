import random
from datetime import date, timedelta

import pytest

from invoicecheck.checkdigit import is_valid_registration_number
from invoicecheck.normalize import parse_date
from invoicecheck.registry import Registry, name_match
from invoicecheck.synth.align import missing_values, printed_values
from invoicecheck.synth.invoice import DATE_STYLES, ISSUE_KINDS, fmt_date, make_invoice, tax_check
from invoicecheck.synth.issuers import build_issuers, build_registry
from invoicecheck.synth.skins import HOLDOUT_TEMPLATES, TRAIN_TEMPLATES


@pytest.fixture(scope="module")
def world():
    rng = random.Random(5)
    issuers = build_issuers(rng, {"train": 12, "test": 6})
    registry = build_registry(rng, issuers, 300)
    return rng, issuers, registry, Registry.from_records(registry)


def test_issuers_are_valid_unique_and_disjoint_across_splits(world):
    _, issuers, _, _ = world
    assert all(is_valid_registration_number(i.reg_no) for i in issuers)
    assert len({i.reg_no for i in issuers}) == len(issuers) and len({i.name for i in issuers}) == len(issuers)
    assert {i.split for i in issuers} == {"train", "test"}


def test_registry_has_every_issuer_active_plus_decoys(world):
    _, issuers, registry, reg = world
    assert reg.count() == len(issuers) + 300
    for i in issuers:
        assert reg.status(i.reg_no, "2026-06-01") == "valid" and name_match(i.name, reg.lookup(i.reg_no).name) == "exact"
    assert {r.process for r in registry} == {"01", "03", "04"}


def test_clean_invoices_pass_every_check(world):
    rng, issuers, registry, reg = world
    for k in range(200):
        iss = rng.choice(issuers)
        g = make_invoice(rng, k, "train", iss, "株式会社受取", "h_classic__k0", registry)
        assert tax_check(g).ok and g["issue_date"] >= iss.registered
        num = g["issuer"]["registration_number"]
        assert is_valid_registration_number(num) and reg.status(num, g["issue_date"]) == "valid"
        assert name_match(g["issuer"]["name"], reg.lookup(num).name) == "exact"


@pytest.mark.parametrize("kind", ISSUE_KINDS)
def test_each_injected_issue_is_caught_by_the_intended_check(world, kind):
    rng, issuers, registry, reg = world
    for k in range(60):
        g = make_invoice(rng, k, "train", rng.choice(issuers), "株式会社受取", "h_classic__k0", registry, issue=kind)
        num, d = g["issuer"]["registration_number"], g["issue_date"]
        assert g["document_issues"] == [kind]
        if kind == "reg_no_check_digit":
            assert not is_valid_registration_number(num)
        elif kind == "reg_no_unregistered":
            assert is_valid_registration_number(num) and reg.status(num, d) == "not_found"
        elif kind == "reg_no_revoked":
            assert reg.status(num, d) == "revoked"
        elif kind == "reg_no_other_company":
            assert reg.status(num, d) == "valid" and name_match(g["issuer"]["name"], reg.lookup(num).name) == "different"
        else:
            assert "tax_mismatch" in tax_check(g).errors


@pytest.mark.parametrize("style", DATE_STYLES)
def test_every_printed_date_style_parses_back(style):
    rng = random.Random(0)
    for _ in range(200):
        iso = (date(2023, 10, 1) + timedelta(days=rng.randint(0, 1095))).isoformat()
        assert parse_date(fmt_date(iso, style)) == iso


def test_alignment_check_finds_missing_values(world):
    rng, issuers, registry, _ = world
    g = make_invoice(rng, 1, "train", issuers[0], "株式会社受取", "h_classic__k0", registry)
    page = " ".join(printed_values(g))
    assert missing_values(g, page) == []
    assert missing_values(g, page.replace(g["issuer"]["registration_number"], "")) == [g["issuer"]["registration_number"]]


def test_template_sets_do_not_overlap():
    assert len(TRAIN_TEMPLATES) == 20 and len(HOLDOUT_TEMPLATES) == 4
    assert not set(TRAIN_TEMPLATES) & set(HOLDOUT_TEMPLATES)
    assert not {t.split("__")[0] for t in HOLDOUT_TEMPLATES} & {t.split("__")[0] for t in TRAIN_TEMPLATES}
