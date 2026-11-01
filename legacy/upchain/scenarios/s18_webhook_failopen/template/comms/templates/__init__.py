"""Message templates. Copy is owned by the CX content team; change wording in catalog.py only with their review."""

from string import Template

from comms.templates.catalog import CATALOG


class TemplateError(KeyError):
    pass


def render(name: str, **params: str) -> tuple[str, str]:
    """(subject, body) for a template; the subject is empty for SMS templates."""
    try:
        entry = CATALOG[name]
    except KeyError:
        raise TemplateError(f"unknown template {name!r}") from None
    missing = sorted(set(entry["params"]) - set(params))
    if missing:
        raise TemplateError(f"template {name!r} needs {', '.join(missing)}")
    subject = Template(entry.get("subject", "")).substitute(params)
    body = Template(entry["body"]).substitute(params)
    return subject, body


def channel_of(name: str) -> str:
    return CATALOG[name]["channel"]
