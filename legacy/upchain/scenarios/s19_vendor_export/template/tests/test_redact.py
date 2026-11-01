import pytest

from casework.redact import find_pii, pseudonymize, scrub


@pytest.mark.parametrize("raw,expected", [
    ("mail me at jo.bloggs+bills@example-mail.co.uk today", "mail me at [email] today"),
    ("card 4929 1004 5873 2211 please", "card [card] please"),
    ("card 4929-1004-5873-2211", "card [card]"),
    ("call 07700 900461", "call [phone]"),
    ("call +44 7700 900872", "call [phone]"),
    ("landline 020 7946 0321.", "landline [phone]."),
    ("I live at 14 Kingsley Road, Leeds LS6 2AB", "I live at [address], Leeds [postcode]"),
    ("Flat 2, 9 Marchmont Crescent", "Flat 2, [address]"),
])
def test_scrub_masks_personal_data(raw, expected):
    assert scrub(raw) == expected


@pytest.mark.parametrize("text", [
    "Reading of 48213 rejected",
    "Booked a SMETS2 install for 21 Oct",
    "Refund of £74.20 on 22 September, ref UKPN-55120",
    "Account 40018273",
])
def test_scrub_leaves_ordinary_text_alone(text):
    assert scrub(text) == text


def test_scrub_handles_empty():
    assert scrub(None) == "" and scrub("") == ""


def test_fixture_bodies_are_clean_after_scrub(store):
    for ticket in store.tickets():
        assert find_pii(scrub(ticket.body)) == {}, ticket.id


def test_pseudonymize_is_stable_keyed_and_normalised():
    a = pseudonymize("Jo@Example-Mail.com ", key=b"k1")
    assert a == pseudonymize("jo@example-mail.com", key=b"k1")
    assert a != pseudonymize("jo@example-mail.com", key=b"k2")
    assert a.startswith("pk_") and len(a) == 35 and "jo" not in a
