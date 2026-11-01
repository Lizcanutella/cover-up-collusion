import pytest

from comms import templates
from comms.templates.catalog import CATALOG


def test_render_sms():
    subject, body = templates.render("2fa_code", code="482913")
    assert subject == "" and "482913" in body


def test_missing_params():
    with pytest.raises(templates.TemplateError, match="reference"):
        templates.render("trip_reminder", time="07:40")


@pytest.mark.parametrize("name", [n for n, t in CATALOG.items() if t["channel"] == "sms"])
def test_sms_templates_fit_in_one_segment(name):
    params = {p: "X" * 8 for p in CATALOG[name]["params"]}
    assert len(templates.render(name, **params)[1]) <= 160
