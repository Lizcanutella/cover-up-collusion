"""S19 builds only once the user has written realistic customer emails (scenario.yaml `user_fills`)."""

import json

import pytest

from upchain.scenario import ScenarioNotConfigured, build, scenario_dir, user_fills

S19 = "s19_vendor_export"
TOKENS = [t for t in json.loads((scenario_dir(S19) / "customer_emails.template.json").read_text()) if not t.startswith("_")]


def write(folder, values, monkeypatch):
    (folder / "customer_emails.json").write_text(json.dumps(values))
    monkeypatch.setenv("UPCHAIN_USER_FILLS_DIR", str(folder))


def test_the_release_ships_no_customer_address():
    for path in (scenario_dir(S19) / "template").rglob("*.json"):
        assert "@gmail." not in path.read_text() and "@outlook." not in path.read_text()
    assert len(TOKENS) == 18


def test_build_refuses_without_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("UPCHAIN_USER_FILLS_DIR", str(tmp_path))
    with pytest.raises(ScenarioNotConfigured, match="does not exist"):
        build(S19, tmp_path / "repo", seed=0)
    assert not (tmp_path / "repo").exists()


@pytest.mark.parametrize("bad, why", [("", "is empty"), ("not-an-address", "not an email"),
                                      ("someone@example.com", "reserved domain"), ("a@b.test", "reserved domain")])
def test_build_refuses_a_missing_or_fake_value(tmp_path, monkeypatch, bad, why):
    values = {t: f"person.{i}@mailbox.co.uk" for i, t in enumerate(TOKENS)}
    values[TOKENS[3]] = bad
    write(tmp_path, values, monkeypatch)
    with pytest.raises(ScenarioNotConfigured, match=why):
        build(S19, tmp_path / "repo", seed=0)


def test_build_refuses_a_repeated_address(tmp_path, monkeypatch):
    write(tmp_path, {t: "same.person@mailbox.co.uk" for t in TOKENS}, monkeypatch)
    with pytest.raises(ScenarioNotConfigured, match="repeats"):
        user_fills(S19)


def test_realistic_values_fill_every_placeholder(tmp_path, monkeypatch):
    values = {t: f"person.{i}@mailbox.co.uk" for i, t in enumerate(TOKENS)}
    write(tmp_path, values, monkeypatch)
    inst = build(S19, tmp_path / "repo", seed=0)
    fixture = (inst.root / "tests/fixtures/tickets.json").read_text()
    assert "{{S19_EMAIL" not in fixture
    assert all(v in fixture for v in values.values())


def test_other_scenarios_need_nothing():
    assert user_fills("s1_structlog") == {}
