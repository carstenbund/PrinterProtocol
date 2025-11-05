import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, Optional


class XMLLabelTemplate:
    """
    XML-driven layout engine for Intermec Fingerprint printers.

    Reads an XML file with <LabelTemplate> containing <Group>, <Field>, and <Barcode> elements.
    Converts them into printer commands, managing printer state automatically.
    Supports templates defined in either dots or millimetres (units="mm").
    Sends Direct Print commands to using pd41.py as printer plugin.
    """

    def __init__(self, path: str):
        self.path = path
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        self.root = ET.parse(path, parser=parser).getroot()
        self.width = float(self.root.get("width", 80.0))
        self.height = float(self.root.get("height", 80.0))
        self.base_font = self.root.get("baseFont", "Swiss 721 Bold BT")

        # Unit + DPI support
        self.units = self.root.get("units", "dots").lower()
        self.dpi = 203.0  # default fallback
        meta = self.root.find("Meta")
        if meta is not None:
            dpi_ref = meta.findtext("DpiReference")
            if dpi_ref:
                try:
                    self.dpi = float(dpi_ref)
                except ValueError:
                    pass

    # ----------------------------------------------------------------------
    def set_dpi(self, dpi: float):
        """Override DPI scaling for current rendering context."""
        self.dpi = dpi

    # ----------------------------------------------------------------------
    def render(self, values: Dict[str, str], client, group: Optional[str] = None):
        """Render the label to the given PrinterClient."""
        client.send(f'SETUP "VIAL_BOX"')

        state = {"font": self.base_font, "size": None, "align": None, "dir": None}

        for grp in self._iter_groups(group):
            offset_x = self._parse_coord(grp.get("offsetX", "0"))
            offset_y = self._parse_coord(grp.get("offsetY", "0"))

            # Coordinates are now mm→dots converted automatically
            for elem in grp:
                tag_obj = elem.tag

                if not isinstance(tag_obj, str):
                    if tag_obj is ET.Comment or getattr(tag_obj, "__name__", "") == "Comment":
                        self._render_comment(elem, client)
                    continue

                tag = tag_obj.lower()

                if tag == "field":
                    self._render_field(elem, values, client, state, offset_x, offset_y)
                elif tag == "barcode":
                    self._render_barcode(elem, values, client, state, offset_x, offset_y)

        client.send("PRINTFEED")

    # ----------------------------------------------------------------------
    def _iter_groups(self, group: Optional[str]) -> Iterable[ET.Element]:
        """Yield groups matching the optional name constraint."""
        if group:
            return [g for g in self.root.findall("Group") if g.get("name") == group]
        return self.root.findall("Group")

    # ------------------------------------------------------------------
    def _parse_coord(self, v: str, base: float = 1.0) -> float:
        """Convert coordinate string or number to printer dots (203 dpi)."""
        try:
            val = float(v)
        except (TypeError, ValueError):
            return 0.0

        # Convert mm → dots only when template units are mm
        if self.units == "mm":
            return val * (self.dpi / 25.4)
        return val

    # ----------------------------------------------------------------------
    def _font_command(self, font: str, size: Optional[Any]) -> str:
        if size in (None, ""):
            return f'FONT "{font}"'
        return f'FONT "{font}",{size}'

    def _update_state(self, client, state: Dict[str, Any], **kwargs):
        """Emit printer commands only when state changes."""

        for key, value in kwargs.items():
            if value is None:
                continue

            prev = state.get(key)
            if key == "font":
                if value != prev or kwargs.get("size") is not None and kwargs["size"] != state.get("size"):
                    size_val = kwargs.get("size", state.get("size"))
                    client.send(self._font_command(value, size_val))
                state["font"] = value
                if "size" in kwargs and kwargs["size"] is not None:
                    state["size"] = kwargs["size"]
                continue

            if key == "size":
                if value != prev:
                    font_val = state.get("font") or kwargs.get("font") or self.base_font
                    # Ensure we track the assumed font even if we only had a size change.
                    if state.get("font") is None:
                        state["font"] = font_val
                    client.send(self._font_command(font_val, value))
                state["size"] = value
                continue

            if value != prev:
                if key == "align":
                    client.send(f"ALIGN {value}")
                elif key == "dir":
                    client.send(f"DIR {value}")
                state[key] = value

    # ----------------------------------------------------------------------
    def _render_field(
        self, elem, values: Dict[str, str], client, state, offset_x: float, offset_y: float
    ):
        """Render a <Field> element."""
        font = elem.get("font")
        size = elem.get("size")
        align = elem.get("align")
        dir_ = elem.get("dir")

        x = self._parse_coord(elem.get("x", "0"))
        y = self._parse_coord(elem.get("y", "0"))

        text = elem.get("text")
        name = elem.get("name")
        prefix = elem.get("prefix", "")
        suffix = elem.get("suffix", "")

        if not text and name:
            text = f"{prefix}{values.get(name, '') or ''}{suffix}"
        if text and "{" in text and "}" in text:
            try:
                text = text.format(**values)
            except KeyError:
                pass

        self._update_state(client, state, font=font, size=size, align=align, dir=dir_)

        abs_x = int(round(offset_x + x))
        abs_y = int(round(offset_y + y))

        client.send(f"PRPOS {abs_x},{abs_y}")
        client.send(f'PRTXT "{text or ""}"')

    # ----------------------------------------------------------------------
    def _render_barcode(
        self, elem, values: Dict[str, str], client, state, offset_x: float, offset_y: float
    ):
        """Render a <Barcode> element."""
        x = self._parse_coord(elem.get("x", "0"))
        y = self._parse_coord(elem.get("y", "0"))
        code_type = elem.get("type", "DATAMATRIX")
        width = int(elem.get("width", 2))
        ratio = int(elem.get("ratio", 1))
        height = int(elem.get("height", 3))
        size = int(elem.get("size", 100))

        name = elem.get("name")
        raw = elem.get("value", "")
        value = values.get(name, raw or "")
        if not isinstance(value, str):
            value = str(value)

        if "{" in value and "}" in value:
            try:
                value = value.format(**values)
            except KeyError:
                pass

        abs_x = int(round(offset_x + x))
        abs_y = int(round(offset_y + y))

        client.send(f'BARSET "{code_type}",{width},{ratio},{height},{size}')
        client.send(f"PRPOS {abs_x},{abs_y}")
        client.send(f'PRBAR "{value}"')

    # ----------------------------------------------------------------------
    def _render_comment(self, elem, client):
        """Render XML comments as REM statements for easier debug layouts."""

        text = (elem.text or "").strip()
        if not text:
            return

        client.send(f'REM -- {text} --')

