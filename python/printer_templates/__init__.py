"""Printer protocol template registry and helpers."""

from __future__ import annotations

from .registry import get_template, list_templates, render_template
from .xml_loader import XmlCommandTemplate

__all__ = [
    "XmlCommandTemplate",
    "get_template",
    "list_templates",
    "render_template",
]
