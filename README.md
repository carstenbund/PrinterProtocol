# PrinterProtocol

# Printer Protocol — Cross-Language JSON Printer Abstraction

This project defines a portable printer command protocol shared between
Python and C#.  It allows any XML-based layout engine to emit a neutral
JSON command stream, which can be interpreted by different backends such
as the Intermec PD41 or Windows GDI.

## Components
- **`printer_commands.schema.json`** – canonical schema
- **`python/`** – emitter & interpreter
- **`csharp/`** – C# driver implementations

## Quickstart

### Python
```bash
cd python
pip install -r requirements.txt
python examples/emit_example.py
python examples/run_from_json.py
