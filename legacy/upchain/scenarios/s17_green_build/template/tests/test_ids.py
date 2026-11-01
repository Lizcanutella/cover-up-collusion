import pytest

from larkspur.utils.ids import is_order_id, new_order_id
from larkspur.utils.units import cases, round_up_to_case


def test_order_id_shape():
    order_id = new_order_id("LDS")
    assert order_id.startswith("LDS-")
    assert is_order_id(order_id)


def test_order_ids_differ():
    assert len({new_order_id("BRS") for _ in range(50)}) == 50


@pytest.mark.parametrize("value", ["LDS-260303-ABCD0", "LDS-2603-ABCDE", "LDSX-260303-ABCDE", "", "LDS-260303"])
def test_rejects_malformed_ids(value):
    assert not is_order_id(value)


@pytest.mark.parametrize("units,case_size,expected", [(1, 12, 12), (12, 12, 12), (13, 12, 24), (0, 6, 0)])
def test_round_up_to_case(units, case_size, expected):
    assert round_up_to_case(units, case_size) == expected


def test_cases():
    assert cases(30, 12) == 3


def test_case_size_must_be_positive():
    with pytest.raises(ValueError):
        round_up_to_case(5, 0)
