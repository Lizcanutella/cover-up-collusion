from ledgerly.cli import main
from ledgerly.storage import Storage


def test_create_then_list(tmp_path, store):
    path = tmp_path / "data.json"
    store.path = path
    store.save()
    assert main(["--data", str(path), "create", "C001", "--line", "Widget:2:10.50"]) == 0
    assert main(["--data", str(path), "list"]) == 0
    assert len(Storage(path).list_invoices()) == 1


def test_unknown_customer_returns_error_code(tmp_path):
    path = tmp_path / "empty.json"
    assert main(["--data", str(path), "create", "NOPE", "--line", "x:1:1"]) == 2
