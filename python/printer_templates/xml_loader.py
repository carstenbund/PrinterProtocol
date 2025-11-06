"""XML template adapter for the printer protocol JSON emitter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping
import xml.etree.ElementTree as ET

from printer_protocol import JsonCommandEmitter


@dataclass
class _RenderState:
    font: str | None = None
    size: float | None = None
    align: str | None = None
    direction: str | None = None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def _emit_command(emitter: JsonCommandEmitter, command_name: str, **kwargs: Any) -> Dict[str, Any]:
    command = emitter.emit(command_name)
    if kwargs:
        args = command.setdefault("args", {})
        args.update(kwargs)
    return command


class XmlCommandTemplate:
    """Convert legacy XML label templates into JSON printer protocol payloads."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        self.root = ET.parse(self.path, parser=parser).getroot()

        self.label_name = self.root.get("name", self.path.stem)
        self.width = _to_float(self.root.get("width"))
        self.height = _to_float(self.root.get("height"))
        self.units = self.root.get("units", "mm")
        self.base_font = self.root.get("baseFont", "Swiss 721 Bold BT")

        self._meta = self.root.find("Meta")
        self.dpi = self._read_dpi(self._meta)
        self._description = self._build_description(self._meta)

    # ------------------------------------------------------------------
    def render(self, values: Mapping[str, Any], *, version: str = "1.0") -> Dict[str, Any]:
        """Render the template with the provided substitution values."""

        emitter = JsonCommandEmitter(source=self.path.name, version=version)
        emitter.set_layout(
            width=self.width,
            height=self.height,
            units=self.units,
            origin="bottom-left",
            y_direction="up",
            dpi=self.dpi,
        )
        if self._description:
            emitter.document["description"] = self._description

        _emit_command(emitter, "Setup", name=self.label_name)

        state = _RenderState()
        value_map = {k: "" if v is None else str(v) for k, v in values.items()}

        for group in self.root.findall("Group"):
            offset_x = _to_float(group.get("offsetX") or group.get("offsetx"))
            offset_y = _to_float(group.get("offsetY") or group.get("offsety"))

            for elem in group:
                if not isinstance(elem.tag, str):
                    comment = _normalise_text(elem.text)
                    if comment:
                        emitter.emit("Comment", text=comment)
                    continue

                tag = elem.tag.lower()
                if tag == "field":
                    self._render_field(emitter, elem, value_map, state, offset_x, offset_y)
                elif tag == "barcode":
                    self._render_barcode(emitter, elem, value_map, state, offset_x, offset_y)

        emitter.emit("PrintFeed")
        return emitter.to_dict()

    # ------------------------------------------------------------------
    def _render_field(
        self,
        emitter: JsonCommandEmitter,
        elem: ET.Element,
        values: Mapping[str, str],
        state: _RenderState,
        offset_x: float,
        offset_y: float,
    ) -> None:
        font = elem.get("font") or self.base_font
        size_attr = elem.get("size")
        size: float | None
        if size_attr is not None and str(size_attr).strip() != "":
            size = _to_float(size_attr, state.size or 0.0)
        else:
            size = state.size
        align = elem.get("align")
        direction = elem.get("dir")

        self._update_state(emitter, state, font=font, size=size, align=align, direction=direction)

        x = offset_x + _to_float(elem.get("x"))
        y = offset_y + _to_float(elem.get("y"))
        text = self._resolve_text(elem, values)

        emitter.emit("MoveTo", x=x, y=y)
        emitter.emit("DrawText", text=text)

    # ------------------------------------------------------------------
    def _render_barcode(
        self,
        emitter: JsonCommandEmitter,
        elem: ET.Element,
        values: Mapping[str, str],
        state: _RenderState,
        offset_x: float,
        offset_y: float,
    ) -> None:
        # Barcodes typically inherit alignment/direction from surrounding fields.
        self._update_state(emitter, state, align=elem.get("align"), direction=elem.get("dir"))

        x = offset_x + _to_float(elem.get("x"))
        y = offset_y + _to_float(elem.get("y"))

        name = elem.get("name")
        raw_value = elem.get("value", "")
        value = values.get(name or "", raw_value)

        emitter.emit("MoveTo", x=x, y=y)
        emitter.emit(
            "DrawBarcode",
            value=value or "",
            type=elem.get("type", "DATAMATRIX"),
            width=int(_to_float(elem.get("width"), 1)),
            ratio=int(_to_float(elem.get("ratio"), 1)),
            height=int(_to_float(elem.get("height"), 1)),
            size=int(_to_float(elem.get("size"), 100)),
        )

    # ------------------------------------------------------------------
    def _update_state(
        self,
        emitter: JsonCommandEmitter,
        state: _RenderState,
        *,
        font: str | None = None,
        size: float | None = None,
        align: str | None = None,
        direction: str | None = None,
    ) -> None:
        if font or size is not None:
            chosen_font = font or state.font or self.base_font
            chosen_size = size if size is not None else state.size
            if chosen_size is None:
                chosen_size = state.size or 0.0
            if state.font != chosen_font or state.size != chosen_size:
                _emit_command(emitter, "SetFont", name=chosen_font, size=float(chosen_size))
                state.font = chosen_font
                state.size = float(chosen_size)
        if align is not None and align != state.align:
            emitter.emit("SetAlignment", align=str(align))
            state.align = str(align)
        if direction is not None and direction != state.direction:
            emitter.emit("SetDirection", direction=str(direction))
            state.direction = str(direction)

    # ------------------------------------------------------------------
    def _resolve_text(self, elem: ET.Element, values: Mapping[str, str]) -> str:
        text = elem.get("text")
        if text:
            return self._format(text, values)

        name = elem.get("name") or ""
        prefix = elem.get("prefix", "")
        suffix = elem.get("suffix", "")

        value = values.get(name, "")
        composed = f"{prefix}{value}{suffix}"
        return self._format(composed, values)

    # ------------------------------------------------------------------
    def _format(self, template: str, values: Mapping[str, str]) -> str:
        if "{" in template and "}" in template:
            try:
                return template.format(**values)
            except (KeyError, ValueError):  # pragma: no cover - best effort formatting
                return template
        return template

    # ------------------------------------------------------------------
    def _read_dpi(self, meta: ET.Element | None) -> float | None:
        if meta is None:
            return None
        dpi_text = meta.findtext("DpiReference")
        if dpi_text is None:
            return None
        try:
            return float(dpi_text)
        except ValueError:  # pragma: no cover - defensive guard
            return None

    # ------------------------------------------------------------------
    def _build_description(self, meta: ET.Element | None) -> str:
        if meta is None:
            return ""
        parts = []
        version = _normalise_text(meta.findtext("Version"))
        author = _normalise_text(meta.findtext("Author"))
        date = _normalise_text(meta.findtext("Date"))
        desc = _normalise_text(meta.findtext("Description"))

        header_bits = []
        if version:
            header_bits.append(f"version {version}")
        if author:
            header_bits.append(f"by {author}")
        if date:
            header_bits.append(f"({date})")
        header = " ".join(header_bits).strip()
        if header:
            parts.append(header)
        if desc:
            parts.append(desc)
        return " -- ".join(parts)
