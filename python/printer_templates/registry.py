"""Template registry for the printer protocol."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Mapping

from .xml_loader import XmlCommandTemplate

_DATA_DIR = Path(__file__).resolve().parent / "data"

_TEMPLATE_FILES: Dict[str, Path] = {
    "scleral_v3": _DATA_DIR / "scleral_v3.xml",
    "scleral_v4": _DATA_DIR / "scleral_v4.xml",
}


def list_templates() -> Iterable[str]:
    """Return the available template names."""

    return sorted(_TEMPLATE_FILES.keys())


@lru_cache(maxsize=None)
def get_template(name: str) -> XmlCommandTemplate:
    """Return a parsed template by name."""

    try:
        path = _TEMPLATE_FILES[name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        options = ", ".join(sorted(_TEMPLATE_FILES))
        raise KeyError(f"Unknown template '{name}'. Available templates: {options}") from exc
    return XmlCommandTemplate(path)


def render_template(name: str, values: Mapping[str, object]):
    """Render a template to a JSON command payload."""

    template = get_template(name)
    return template.render(values)
