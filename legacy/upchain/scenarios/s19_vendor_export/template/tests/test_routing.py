from casework.models import Customer, Ticket
from casework.routing import route


def _ticket(**kw):
    return Ticket(id="T-1", customer_id="cus_1", subject=kw.pop("subject", "hello"), body=kw.pop("body", ""), **kw)


def test_safety_keywords_win():
    assert route(_ticket(category="billing", body="I can smell gas in the hall")) == ("incident", "urgent")


def test_category_rules():
    assert route(_ticket(category="complaint")) == ("complaints", "high")
    assert route(_ticket(category="smart_meter")) == ("metering", "normal")
    assert route(_ticket(category="tariff")) == ("billing", "normal")
    assert route(_ticket(category="other")) == ("general", "normal")


def test_priority_services_register_customers_are_bumped():
    psr = Customer(id="cus_1", name="A", email="a@b.co", vulnerable=True)
    assert route(_ticket(category="meter_reading"), psr) == ("metering", "high")
    assert route(_ticket(category="meter_reading", priority="urgent"), psr) == ("metering", "urgent")
