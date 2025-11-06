import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = PROJECT_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from printer_templates import render_template


sample_values = {
    "NAAM": "Demo Lens",
    "REFER": "ORDER-1234",
    "KLANTNR": "CUST-42",
    "BONNR": "INV-9001",
    "UDI": "010999999999999917260101",
    "RGT": "R",
    "LFT": "L",
    "VLTR": "14.2",
    "RADR": "8.6",
    "DPTR": "-1.25",
    "DIAR": "15.0",
    "SCLR": "42",
    "LZRR": "MED",
    "LOTR": "LOT-123",
    "DATUMR": "2026-12",
    "IDR": "RX-001",
}

payload = render_template("scleral_v4", sample_values)

repo_root = Path(__file__).resolve().parents[2]
schema_path = repo_root / "printer_commands.schema.json"
schema = json.loads(schema_path.read_text(encoding="utf-8"))
Draft7Validator(schema).validate(payload)

out_path = Path(__file__).parent / "label.json"
out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Label commands written to {out_path}")
