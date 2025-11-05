"""Shared printer protocol primitives for emitters and drivers.

This module exposes two primary helper classes:
- :class:`JsonCommandEmitter` for building a JSON command payload that
  adheres to :mod:`printer_commands.schema.json`.
- :class:`JsonCommandInterpreter` for dispatching those commands against
  a :class:`PrinterDriver` implementation.

Both utilities are intentionally lightweight so they can run on minimal
Python installations that are often paired with industrial printers.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

from jsonschema import Draft7Validator


class PrinterDriver(ABC):
    """Abstract base class describing the printer command surface."""

    dpi: float = 203.0

    @abstractmethod
    def setup(self, name: str) -> None:
        """Prepare the printer for a named label format."""

    @abstractmethod
    def set_font(self, name: str, size: float) -> None:
        """Select a font family and point size."""

    @abstractmethod
    def set_alignment(self, align: str) -> None:
        """Adjust horizontal alignment for subsequent operations."""

    @abstractmethod
    def set_direction(self, direction: str) -> None:
        """Switch the print direction, e.g. normal or reverse."""

    @abstractmethod
    def move_to(self, x: float, y: float) -> None:
        """Move the print head to an absolute position."""

    @abstractmethod
    def draw_text(self, text: str) -> None:
        """Render text at the current cursor position."""

    @abstractmethod
    def draw_barcode(
        self,
        value: str,
        type: str,
        width: int,
        ratio: int,
        height: int,
        size: int,
    ) -> None:
        """Render a one-dimensional barcode."""

    @abstractmethod
    def comment(self, text: str) -> None:
        """Log a diagnostic comment for debugging purposes."""

    @abstractmethod
    def print_feed(self) -> None:
        """Advance the media and trigger printing."""

    @abstractmethod
    def get_dpi(self) -> float:
        """Return the device dots-per-inch."""


class JsonCommandEmitter:
    """Helper for building protocol-compliant command payloads."""

    def __init__(self, source: Optional[str] = None, version: str = "1.0") -> None:
        self.version = version
        self.document: Dict[str, Any] = {}
        if source:
            self.document["source"] = source
        self._commands: list[Dict[str, Any]] = []

    def emit(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        """Append a command entry to the payload."""

        command: Dict[str, Any] = {"name": name, "args": kwargs or {}}
        self._commands.append(command)
        return command

    def to_dict(self) -> Dict[str, Any]:
        """Return the payload as a dictionary."""

        payload: Dict[str, Any] = {"version": self.version, "commands": list(self._commands)}
        if self.document:
            payload["document"] = dict(self.document)
        return payload

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise the payload to a JSON string."""

        return json.dumps(self.to_dict(), indent=indent)

    def validate(self, schema_path: Path | str) -> None:
        """Validate the payload against the canonical schema."""

        schema_data = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        Draft7Validator(schema_data).validate(self.to_dict())


class JsonCommandInterpreter:
    """Dispatch JSON commands against a :class:`PrinterDriver`."""

    def __init__(self, driver: PrinterDriver) -> None:
        self.driver = driver
        self._dispatch = {
            "Setup": driver.setup,
            "SetFont": driver.set_font,
            "SetAlignment": driver.set_alignment,
            "SetDirection": driver.set_direction,
            "MoveTo": driver.move_to,
            "DrawText": driver.draw_text,
            "DrawBarcode": driver.draw_barcode,
            "Comment": driver.comment,
            "PrintFeed": driver.print_feed,
        }

    def run(self, payload: Mapping[str, Any] | str | Path) -> None:
        """Execute commands from a mapping, JSON string, or file path."""

        data = self._coerce_payload(payload)
        commands = data.get("commands", [])
        if not isinstance(commands, Iterable):
            raise TypeError("commands collection must be iterable")

        if hasattr(self.driver, "__enter__") and hasattr(self.driver, "__exit__"):
            with self.driver:  # type: ignore[misc]
                self._execute(commands)
        else:
            self._execute(commands)

    def _execute(self, commands: Iterable[Mapping[str, Any]]) -> None:
        for entry in commands:
            if not isinstance(entry, Mapping):
                raise TypeError("command entries must be mappings")
            name = entry.get("name")
            if not isinstance(name, str):
                raise ValueError("command name must be a string")
            args = entry.get("args", {})
            if not isinstance(args, MutableMapping):
                raise TypeError("command args must be a mapping")

            handler = self._dispatch.get(name)
            if handler is None:
                raise KeyError(f"Unsupported command: {name}")
            handler(**dict(args))

    def _coerce_payload(self, payload: Mapping[str, Any] | str | Path) -> Mapping[str, Any]:
        if isinstance(payload, Mapping):
            return payload
        if isinstance(payload, Path):
            text = payload.read_text(encoding="utf-8")
            return json.loads(text)
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return json.loads(Path(payload).read_text(encoding="utf-8"))
        raise TypeError("Unsupported payload type")

    @staticmethod
    def run_file(path: Path | str, driver: PrinterDriver) -> None:
        """Convenience helper to run a command file directly."""

        JsonCommandInterpreter(driver).run(Path(path))


__all__ = [
    "PrinterDriver",
    "JsonCommandEmitter",
    "JsonCommandInterpreter",
]
