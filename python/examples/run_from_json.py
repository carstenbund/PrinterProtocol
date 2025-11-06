import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = PROJECT_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from drivers.gdi_driver_stub import GdiDriverStub
from printer_protocol import JsonCommandInterpreter


label_path = Path(__file__).parent / "label.json"
commands = json.loads(label_path.read_text(encoding="utf-8"))

driver = GdiDriverStub()
JsonCommandInterpreter(driver).run(commands)
