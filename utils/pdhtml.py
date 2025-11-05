import html
import xml.etree.ElementTree as ET
from string import Formatter
from typing import Dict, Iterable, Mapping, Union

class LabelRenderer:
    """
    Minimal XML label preview renderer.
    Maps printer-space coordinates (bottom-left origin)
    into screen-space coordinates (top-left origin).
    """

    def __init__(self, xml_path: str, dpi: float = 203.0):
        self.root = ET.parse(xml_path).getroot()
        self.dpi = dpi
        self.units = self.root.get("units", "mm").lower()
        self.width = float(self.root.get("width", 80))
        self.height = float(self.root.get("height", 60))

    # ----------------------------------------------------------
    def mm_to_dots(self, mm: float) -> float:
        """Convert millimetres to printer dots."""
        return mm * (self.dpi / 25.4)

    def to_dots(self, value: float) -> float:
        """Normalize to dots depending on units."""
        return self.mm_to_dots(value) if self.units == "mm" else value

    # ----------------------------------------------------------
    def parse_length(self, raw: Union[str, float, None], axis: str) -> float:

        """Parse a coordinate/length value supporting percentages and mm."""
        if raw is None:
            return 0.0

        if isinstance(raw, (int, float)):
            value = float(raw)
        else:
            text = raw.strip()
            if text.endswith("%"):
                try:
                    pct = float(text[:-1]) / 100.0
                except ValueError:
                    pct = 0.0
                base = self.width if axis == "x" else self.height
                value = base * pct
            else:
                try:
                    value = float(text)
                except ValueError:
                    value = 0.0

        return value

    # ----------------------------------------------------------
    def _stringify(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _stringify_values(self, values: Mapping[str, object]) -> Dict[str, str]:
        return {k: self._stringify(v) for k, v in values.items()}

    # ----------------------------------------------------------
    def _expand_placeholders(self, template: str, values: Mapping[str, object]) -> str:
        """Safely expand {placeholders} using provided values."""

        class SafeDict(dict):
            def __missing__(self, key):  # type: ignore[override]
                return ""

        if not template or "{" not in template:
            return template or ""

        safe_values = SafeDict(self._stringify_values(values))
        try:
            return Formatter().vformat(template, (), safe_values)
        except Exception:
            return template

    # ----------------------------------------------------------
    def _collect_value(self, elem, values: Mapping[str, object]) -> str:
        name = elem.get("name", "")
        prefix = elem.get("prefix", "")
        suffix = elem.get("suffix", "")
        text = elem.get("text")

        if name and not text:
            raw_value = values.get(name, "")
            text = f"{prefix}{self._stringify(raw_value)}{suffix}"

        text = self._expand_placeholders(text or "", values)
        return text

    # ----------------------------------------------------------
    def _align_rules(self, elem) -> Iterable[str]:
        align = elem.get("align")
        if not align:
            return []

        align_map = {
            "1": "left",
            "2": "center",
            "3": "right",
            "4": "left",
            "5": "center",
            "6": "right",
            "7": "left",
        }
        css = align_map.get(str(align), "left")
        return [f"text-align:{css}"] if css else []

    def _direction_rules(self, elem) -> Iterable[str]:
        dir_value = elem.get("dir")
        if dir_value == "3":
            return ["transform: rotate(-90deg)", "transform-origin: top left"]
        if dir_value == "4":
            return ["writing-mode: vertical-rl"]
        return []

    # ----------------------------------------------------------
    def printer_to_screen(self, x_p, y_p, scale):
        """
        Convert printer coordinates (bottom-left) into screen coordinates (top-left).
        """
        H = self.to_dots(self.height)
        x_s = self.to_dots(x_p) * scale
        y_s = (H - self.to_dots(y_p)) * scale
        return x_s, y_s

    # ----------------------------------------------------------
    def render_html(
        self,
        values: Mapping[str, object],
        scale: float = 1.0,
        show_grid: bool = False,
        grid_step_dots: float = 10.0,
        major_every: int = 5,
    ) -> str:
        """Render label as HTML/CSS, 1:1 preview of printer layout.

        Parameters
        ----------
        values:
            Mapping of field names to their textual content.
        scale:
            Multiplier applied to the printer-dots coordinate system to control
            preview size in CSS pixels.
        show_grid:
            When ``True`` a DPI-derived grid is drawn behind the template to aid
            manual measurements.
        grid_step_dots:
            Size of the minor grid squares expressed in printer dots. For a
            203 DPI template a value of 10 draws a line every 10 printer dots.
        major_every:
            Number of minor squares between thicker major grid lines.
        """
        W = self.to_dots(self.width) * scale
        H = self.to_dots(self.height) * scale

        css_rules = []
        html_parts = []

        # Base container
        container_class = "label-template"
        container_rules = [
            "position: relative",
            f"width:{W:.2f}px",
            f"height:{H:.2f}px",
            "background:white",
            "font-family:'Swiss 721 Bold BT'",
            "overflow:visible",
        ]

        if show_grid and grid_step_dots > 0:
            dot_px = max(scale, 0.1)
            minor_px = max(dot_px * grid_step_dots, 1.0)
            major_every = max(major_every, 1)
            major_px = minor_px * major_every
            grid_minor = "rgba(0, 0, 0, 0.08)"
            grid_major = "rgba(0, 0, 0, 0.18)"
            background_image = (
                "background-image:"
                f"repeating-linear-gradient(to right, {grid_minor} 0, {grid_minor} 1px, transparent 1px, transparent {minor_px:.2f}px),"
                f"repeating-linear-gradient(to bottom, {grid_minor} 0, {grid_minor} 1px, transparent 1px, transparent {minor_px:.2f}px),"
                f"repeating-linear-gradient(to right, {grid_major} 0, {grid_major} 1px, transparent 1px, transparent {major_px:.2f}px),"
                f"repeating-linear-gradient(to bottom, {grid_major} 0, {grid_major} 1px, transparent 1px, transparent {major_px:.2f}px)"
            )
            container_rules.extend([background_image, "background-color:#fff"])

        css_rules.append((f".{container_class}", container_rules))

        if show_grid and grid_step_dots > 0:
            css_rules.extend(
                [
                    (
                        ".label-grid-label",
                        [
                            "position:absolute",
                            "font-size:10px",
                            "color:#555",
                            "pointer-events:none",
                            "font-family:monospace",
                        ],
                    ),
                    (
                        ".label-grid-label.grid-x",
                        [
                            "top:-14px",
                            "transform:translateX(-50%)",
                        ],
                    ),
                    (
                        ".label-grid-label.grid-y",
                        [
                            "left:-34px",
                            "transform:translateY(50%)",
                        ],
                    ),
                    (
                        ".label-grid-axis",
                        [
                            "position:absolute",
                            "left:-34px",
                            "top:-18px",
                            "font-size:10px",
                            "color:#333",
                            "font-family:monospace",
                        ],
                    ),
                ]
            )

        # Render groups and fields
        idx = 0
        for group in self.root.findall("Group"):
            offset_x = self.parse_length(group.get("offsetX", "0"), "x")
            offset_y = self.parse_length(group.get("offsetY", "0"), "y")

            for elem in group:
                tag = elem.tag.lower()
                if tag not in ("field", "barcode"):
                    continue

                x = self.parse_length(elem.get("x", "0"), "x") + offset_x
                y = self.parse_length(elem.get("y", "0"), "y") + offset_y
                x_s, y_s = self.printer_to_screen(x, y, scale)

                size_attr = elem.get("size", "10")
                try:
                    size = float(size_attr)
                except (TypeError, ValueError):
                    size = 10.0
                font_px = (size / 72 * self.dpi) * scale

                if tag == "field":
                    text = self._collect_value(elem, values)
                    text = html.escape(self._stringify(text))
                    class_name = f"label-field-{idx}"
                    html_parts.append(
                        f'<div class="{class_name}">{text}</div>'
                    )
                    extra_rules = list(self._align_rules(elem))
                    extra_rules.extend(self._direction_rules(elem))
                    css_rules.append((
                        f".{class_name}",
                        [
                            "position:absolute",
                            f"left:{x_s:.2f}px",
                            f"top:{y_s:.2f}px",
                            f"font-size:{font_px:.2f}px",
                            *extra_rules,
                        ],
                    ))
                elif tag == "barcode":
                    display_value = self._collect_value(elem, values)
                    if not display_value:
                        fallback = elem.get("value", "")
                        display_value = self._expand_placeholders(fallback, values)
                    display_value = html.escape(self._stringify(display_value))
                    class_name = f"label-barcode-{idx}"
                    html_parts.append(
                        f'<div class="{class_name}"><pre>{display_value}</pre></div>'
                    )
                    css_rules.append((
                        f".{class_name}",
                        [
                            "position:absolute",
                            f"left:{x_s:.2f}px",
                            f"top:{y_s:.2f}px",
                        ],
                    ))
                idx += 1

        if show_grid and grid_step_dots > 0:
            W_dots = self.to_dots(self.width)
            H_dots = self.to_dots(self.height)
            minor_step = grid_step_dots
            major_every = max(major_every, 1)
            major_step = minor_step * major_every

            # Axis labels (origin references printer space)
            html_parts.append('<div class="label-grid-axis">(0,0)</div>')

            # X axis labels (top edge)
            x_index = 0
            while True:
                x_dots = x_index * major_step
                if x_dots > W_dots + 0.1:
                    break
                x_px = x_dots * scale
                class_name = f"label-grid-x-{x_index}"
                html_parts.append(
                    f'<div class="label-grid-label grid-x {class_name}">{x_dots:.0f}</div>'
                )
                css_rules.append((f".{class_name}", [f"left:{x_px:.2f}px"]))
                x_index += 1

            # Y axis labels (left edge, printer origin bottom-left)
            y_index = 0
            while True:
                y_dots = y_index * major_step
                if y_dots > H_dots + 0.1:
                    break
                y_px = (H_dots - y_dots) * scale
                class_name = f"label-grid-y-{y_index}"
                html_parts.append(
                    f'<div class="label-grid-label grid-y {class_name}">{y_dots:.0f}</div>'
                )
                css_rules.append((f".{class_name}", [f"top:{y_px:.2f}px"]))
                y_index += 1

        # Build CSS
        css_text = ["<style>"]
        for selector, rules in css_rules:
            css_text.append(f"{selector} {{")
            for r in rules:
                css_text.append(f"  {r};")
            css_text.append("}")
        css_text.append("</style>")

        # Build HTML
        html_output = (
            "\n".join(css_text)
            + f'\n<div class="{container_class}">\n  '
            + "\n  ".join(html_parts)
            + "\n</div>"
        )
        return html_output


if __name__ == "__main__":
    from pathlib import Path

    from pd41 import build_values_from_order, pretend_feeder

    order = pretend_feeder()
    values = build_values_from_order(order)

    template_path = Path("templates/scleral_107.xml")
    renderer = LabelRenderer(str(template_path), dpi=203)
    html_code = renderer.render_html(
        values,
        scale=1.0,
        show_grid=True,
        grid_step_dots=10.0,
        major_every=5,
    )

    output_path = template_path.with_suffix(".preview.html")
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_code)
    print(f"Preview written to {output_path}")

