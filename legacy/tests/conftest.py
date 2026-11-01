"""The harness's tests build S19 with placeholder customer emails (`user_fills`), unless the user has set
UPCHAIN_USER_FILLS_DIR. The placeholders are at a reserved domain, which `_allow_reserved_domains` permits for tests
only; a real run needs realistic addresses (legacy/README.md)."""

import json
import os

import pytest

from upchain.scenario import scenario_dir


@pytest.fixture(autouse=True, scope="session")
def s19_test_emails(tmp_path_factory):
    if os.environ.get("UPCHAIN_USER_FILLS_DIR"):
        yield
        return
    template = json.loads((scenario_dir("s19_vendor_export") / "customer_emails.template.json").read_text())
    folder = tmp_path_factory.mktemp("fills")
    values = {"_allow_reserved_domains": True}
    values |= {token: f"customer{token[-2:]}@s19-test.invalid" for token in template if not token.startswith("_")}
    (folder / "customer_emails.json").write_text(json.dumps(values))
    os.environ["UPCHAIN_USER_FILLS_DIR"] = str(folder)
    yield
    del os.environ["UPCHAIN_USER_FILLS_DIR"]
