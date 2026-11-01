import pytest

from comms import phone


@pytest.mark.parametrize("raw,expected", [
    ("+44 7700 900123", "+447700900123"),
    ("07700 900123", "+447700900123"),
    ("0044 7700 900123", "+447700900123"),
    ("+1 (415) 555-0134", "+14155550134"),
])
def test_normalise(raw, expected):
    assert phone.normalise(raw) == expected


def test_rejects_garbage():
    with pytest.raises(phone.InvalidNumber):
        phone.normalise("call me")


def test_mask_keeps_country_and_last_two():
    assert phone.mask("+447700900123") == "+44********23"
