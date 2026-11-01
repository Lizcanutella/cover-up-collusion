from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(provider: str, name: str) -> bytes:
    """A fixture's raw bytes, exactly as the provider sent them (signatures are over the raw body)."""
    return (FIXTURES / provider / name).read_bytes()
