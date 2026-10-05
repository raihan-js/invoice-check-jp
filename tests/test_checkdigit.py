import random

import pytest

from invoicecheck.checkdigit import (check_digit, is_valid_corporate_number, is_valid_registration_number,
                                     make_corporate_number, normalize_registration_number)


def test_nta_own_corporate_number_is_valid():
    assert is_valid_corporate_number("7000012050002")      # 国税庁


def test_known_registry_numbers_valid():
    assert is_valid_registration_number("T1000020012131")
    assert is_valid_registration_number("T1010001002431")


def test_changed_digit_is_invalid():
    assert not is_valid_registration_number("T1010001002432")
    assert not is_valid_registration_number("T2010001002431")      # check digit itself changed


def test_normalisation_of_messy_input():
    assert normalize_registration_number("Ｔ－１０１０００１００２４３１") == "T1010001002431"
    assert normalize_registration_number("t 1010001 002431") == "T1010001002431"
    assert normalize_registration_number("T101000100243") is None          # 12 digits
    assert normalize_registration_number("1010001002431") is None          # no T
    assert normalize_registration_number(None) is None


def test_wrong_lengths_rejected():
    assert not is_valid_corporate_number("700001205000")
    assert not is_valid_corporate_number("70000120500022")
    with pytest.raises(ValueError):
        check_digit("12345")


def test_make_corporate_number_round_trip():
    rng = random.Random(0)
    for _ in range(500):
        twelve = "".join(rng.choice("0123456789") for _ in range(12))
        n = make_corporate_number(twelve)
        assert len(n) == 13 and n[0] != "0" and is_valid_corporate_number(n)


def test_check_digit_is_never_zero():
    rng = random.Random(1)
    assert all(1 <= check_digit("".join(rng.choice("0123456789") for _ in range(12))) <= 9 for _ in range(2000))


def test_zero_nine_substitution_is_the_known_blind_spot():
    # the weighted sum is taken mod 9, so changing a digit 0 <-> 9 leaves the check digit unchanged
    n = make_corporate_number("000012050002")
    assert is_valid_corporate_number(n)
    assert n[1] == "0"
    swapped = n[:1] + "9" + n[2:]          # the 0 right after the check digit becomes 9
    assert is_valid_corporate_number(swapped)


def test_other_single_digit_errors_are_detected():
    n = make_corporate_number("123456789012")
    for pos in range(13):
        for d in "0123456789":
            if d == n[pos] or {d, n[pos]} == {"0", "9"}:
                continue
            assert not is_valid_corporate_number(n[:pos] + d + n[pos + 1:])
