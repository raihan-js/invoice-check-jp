import csv

from invoicecheck.registry import Record, Registry, build_db, iter_rows, name_match

A = Record("T1010001002431", "株式会社恵友", "千葉県浦安市舞浜２丁目４１番９号", "01", "2023-10-01", "", "")
B = Record("T1000030200015", "松本市入山辺里山辺財産区", "長野県松本市", "03", "2023-10-01", "", "2024-04-01")
C = Record("T1010001026769", "バンフ・リゾート株式会社", "長野県北佐久郡", "04", "2023-10-01", "2025-12-01", "")


def reg():
    return Registry.from_records([A, B, C])


def test_status_by_invoice_date():
    r = reg()
    assert r.status("T1010001002431", "2024-05-01") == "valid"
    assert r.status("T1010001002431", "2023-09-30") == "not_yet_registered"
    assert r.status("T1000030200015", "2024-03-31") == "valid"
    assert r.status("T1000030200015", "2024-04-01") == "expired"
    assert r.status("T1010001026769", "2025-11-30") == "valid"
    assert r.status("T1010001026769", "2025-12-01") == "revoked"
    assert r.status("T9999999999999", "2024-05-01") == "not_found"


def test_lookup_and_count():
    r = reg()
    assert r.count() == 3 and r.lookup("T1010001002431").name == "株式会社恵友" and r.lookup("T0") is None


def test_name_match_levels():
    assert name_match("株式会社恵友", "株式会社恵友") == "exact"
    assert name_match("(株)恵友", "株式会社恵友") == "exact"
    assert name_match("恵友", "株式会社恵友") == "same_core"
    assert name_match("株式会社恵友商事", "株式会社恵友") == "different"


def _row(seq, reg_no, process, kind, latest, name):
    r = [""] * 24
    r[0], r[1], r[2], r[3], r[4], r[5], r[6] = str(seq), reg_no, process, "0", kind, "1" if kind else "", latest
    r[7], r[11], r[18] = "2023-10-01", "東京都", name
    return r


def test_csv_parsing_keeps_only_current_corporate_rows(tmp_path):
    p = tmp_path / "h_all_test_001.csv"
    rows = [_row(1, "T1010001002431", "01", "2", "1", "株式会社恵友"),
            _row(2, "T1000030200015", "01", "", "0", ""),                  # history row, dropped
            _row(3, "T1000030200015", "03", "2", "1", "財産区"),
            _row(4, "T5000000000000", "01", "1", "1", "個人")]              # individual, dropped
    with open(p, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)
    got = list(iter_rows(p))
    assert [g[0] for g in got] == ["T1010001002431", "T1000030200015"]
    meta = build_db([p], tmp_path / "r.sqlite", "2026-09-30", "2026-10-05")
    assert meta["registrants"] == 2 and meta["redistribution"].startswith("none")
    assert Registry(tmp_path / "r.sqlite").lookup("T1000030200015").process == "03"
