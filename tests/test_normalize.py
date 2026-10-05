from invoicecheck.normalize import normalize_name, parse_date, strip_company_form, to_int_yen


def test_dates_western_and_era():
    assert parse_date("令和5年10月1日") == "2023-10-01"
    assert parse_date("R5.10.1") == "2023-10-01"
    assert parse_date("令和元年5月1日") == "2019-05-01"
    assert parse_date("平成31年4月30日") == "2019-04-30"
    assert parse_date("昭和64年1月7日") == "1989-01-07"
    assert parse_date("２０２３年１０月１日") == "2023-10-01"
    assert parse_date("2023/10/1") == "2023-10-01"


def test_impossible_dates_rejected():
    assert parse_date("令和1年4月30日") is None          # still 平成
    assert parse_date("平成31年5月1日") is None          # already 令和
    assert parse_date("令和5年2月30日") is None
    assert parse_date("来月") is None


def test_yen_amounts():
    assert to_int_yen("￥１，２３４") == 1234
    assert to_int_yen("¥1,234") == 1234
    assert to_int_yen("1,234円") == 1234
    assert to_int_yen("△500") == -500
    assert to_int_yen("無料") is None


def test_company_names():
    assert normalize_name("(株)サンプル　商事") == "株式会社サンプル商事"
    assert normalize_name("㈱サンプル商事") == "株式会社サンプル商事"
    assert strip_company_form("株式会社 サンプル商事") == "サンプル商事"
