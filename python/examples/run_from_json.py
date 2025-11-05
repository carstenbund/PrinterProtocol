import json
from pathlib import Path

from drivers.gdi_driver_stub import GdiDriverStub
from printer_protocol import JsonCommandInterpreter


label_path = Path(__file__).parent / "label.json"
commands = json.loads(label_path.read_text(encoding="utf-8"))

driver = GdiDriverStub()
JsonCommandInterpreter(driver).run(commands)
