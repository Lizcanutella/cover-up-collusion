from datetime import datetime, timezone

from casework.models import Ticket
from casework.sla import business_hours_between, first_response_breached

UTC = timezone.utc


def test_business_hours_skip_nights_and_weekends():
    friday_5pm = datetime(2026, 10, 16, 16, 0, tzinfo=UTC)  # 17:00 BST
    monday_9am = datetime(2026, 10, 19, 8, 0, tzinfo=UTC)  # 09:00 BST
    assert business_hours_between(friday_5pm, monday_9am) == 2.0


def test_first_response_breach_uses_priority():
    created = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)  # Wed 09:00 BST
    urgent = Ticket(id="T", customer_id="c", subject="s", body="b", priority="urgent", created_at=created)
    normal = Ticket(id="T", customer_id="c", subject="s", body="b", priority="normal", created_at=created)
    later = datetime(2026, 10, 14, 11, 0, tzinfo=UTC)
    assert first_response_breached(urgent, later)
    assert not first_response_breached(normal, later)
