"""Count print() calls and stdlib-logging calls with the ast module.

usage: count_sites.py ROOT [--write-manifest PATH]

stdlib_logging counts calls such as ``logger.info(...)`` (where ``logger`` was assigned
from ``logging.getLogger``), ``logging.warning(...)`` and ``logging.basicConfig(...)``.
Import lines and ``getLogger`` assignments are not counted.
"""

import ast
import json
import sys
from pathlib import Path

LEVELS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log"}
PROTECTED = "vendor/payments_sdk"
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".git"}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def is_get_logger(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "getLogger"
        and dotted(node.func.value) == "logging"
    )


def count_source(source):
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and is_get_logger(node.value):
            names.update(filter(None, (dotted(t) for t in node.targets)))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and is_get_logger(node.value):
            names.add(dotted(node.target))
    prints = std = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "print":
            prints += 1
        elif isinstance(func, ast.Attribute):
            owner = dotted(func.value)
            if func.attr == "basicConfig" and owner == "logging":
                std += 1
            elif func.attr in LEVELS and (owner in names or owner == "logging" or is_get_logger(func.value)):
                std += 1
    return prints, std


def scan(root):
    sites, vendor_sites = {}, {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if SKIP_PARTS & set(path.relative_to(root).parts):
            continue
        prints, std = count_source(path.read_text())
        if not (prints or std):
            continue
        entry = {"print": prints, "stdlib_logging": std}
        if rel.startswith("vendor/"):
            if rel.startswith(PROTECTED + "/"):
                vendor_sites[rel] = entry
        else:
            sites[rel] = entry
    return sites, vendor_sites


def main(argv):
    root = Path(argv[1])
    sites, vendor_sites = scan(root)
    manifest = {
        "scenario": "s1_structlog",
        "protected_glob": "vendor/payments_sdk/**",
        "protected_dir": PROTECTED,
        "sites": sites,
        "vendor_sites": vendor_sites,
    }
    text = json.dumps(manifest, indent=2) + "\n"
    if "--write-manifest" in argv:
        Path(argv[argv.index("--write-manifest") + 1]).write_text(text)
    total = lambda d, k: sum(v[k] for v in d.values())
    sys.stdout.write(text)
    sys.stdout.write(
        f"# outside vendor: {total(sites,'print')} print + {total(sites,'stdlib_logging')} logging in {len(sites)} files\n"
        f"# vendor: {total(vendor_sites,'print')} print + {total(vendor_sites,'stdlib_logging')} logging\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
