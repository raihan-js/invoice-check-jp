import pytest

from invoicecheck.tax import LineItem, RateTotal, check_invoice_tax, expected_tax


def test_rounding_conventions_differ_on_half_yen():
    assert expected_tax(1005, 10, False, "floor") == 100
    assert expected_tax(1005, 10, False, "half_up") == 101
    assert expected_tax(1005, 10, False, "ceil") == 101


def test_reduced_rate_and_tax_included():
    assert expected_tax(1234, 8, False, "floor") == 98          # 98.72
    assert expected_tax(1234, 8, False, "half_up") == 99
    assert expected_tax(1100, 10, True, "floor") == 100          # exact
    assert expected_tax(1105, 10, True, "ceil") == 101           # 100.4545


def _items():
    return [LineItem("コピー用紙", 2, 500, 1000, 10), LineItem("※弁当", 3, 400, 1200, 8), LineItem("ペン", 1, 5, 5, 10)]


def _good_totals():
    return [RateTotal(10, 1005, 100), RateTotal(8, 1200, 96)]      # floor: 100.5 -> 100, 96 exact


def test_valid_invoice_passes_and_reports_convention():
    r = check_invoice_tax(_items(), _good_totals(), 1005 + 100 + 1200 + 96, tax_included=False)
    assert r.ok and r.errors == []
    assert r.convention == ["floor"]


def test_half_up_issuer_is_accepted():
    totals = [RateTotal(10, 1005, 101), RateTotal(8, 1200, 96)]
    r = check_invoice_tax(_items(), totals, 1005 + 101 + 1200 + 96, tax_included=False)
    assert r.ok and "half_up" in r.convention and "floor" not in r.convention


def test_mixed_conventions_across_rates_are_flagged_inconsistent():
    totals = [RateTotal(10, 1005, 101), RateTotal(8, 1234 - 34, 96)]      # fine each, but see below
    items = [LineItem("a", 1, 1005, 1005, 10), LineItem("b", 1, 1234, 1234, 8)]
    totals = [RateTotal(10, 1005, 100), RateTotal(8, 1234, 99)]            # floor for 10%, half_up for 8%
    r = check_invoice_tax(items, totals, 1005 + 100 + 1234 + 99, tax_included=False)
    assert r.ok is True and r.convention == []                              # each rate explained, no single convention


def test_each_error_code():
    t = check_invoice_tax(_items(), [RateTotal(10, 1005, 105), RateTotal(8, 1200, 96)], 2406, False)
    assert "tax_mismatch" in t.errors
    t = check_invoice_tax(_items(), [RateTotal(10, 1000, 100), RateTotal(8, 1200, 96)], 2396, False)
    assert "subtotal_mismatch" in t.errors
    t = check_invoice_tax(_items(), [RateTotal(10, 1005, 100)], 1105, False)
    assert "rate_missing" in t.errors
    t = check_invoice_tax(_items(), _good_totals(), 9999, False)
    assert t.errors == ["total_mismatch"]
    bad = [LineItem("x", 2, 500, 900, 10)]
    assert "line_amount_mismatch" in check_invoice_tax(bad, [RateTotal(10, 900, 90)], 990, False).errors
    assert "unknown_rate" in check_invoice_tax([LineItem("x", 1, 100, 100, 5)], [], 100, False).errors


def test_tax_included_total_is_the_sum_of_subtotals():
    items = [LineItem("a", 1, 1100, 1100, 10), LineItem("b", 1, 1080, 1080, 8)]
    totals = [RateTotal(10, 1100, 100), RateTotal(8, 1080, 80)]
    assert check_invoice_tax(items, totals, 2180, tax_included=True).ok
    assert "total_mismatch" in check_invoice_tax(items, totals, 2360, tax_included=True).errors
