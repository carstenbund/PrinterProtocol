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
```

### C#

```bash
cd csharp/PrinterProtocol
dotnet run
```

Both will render or send the same JSON command stream.

## Canonical Layout Orientation

Exactly right — this is one of the few genuinely *non-portable* aspects of printer graphics. Different renderers assume different axis conventions:

| System / Driver                               | Origin      | Y-Direction |
| --------------------------------------------- | ----------- | ----------- |
| **PD41 / Fingerprint**                        | bottom-left | **up**      |
| **ZPL / EPL / ESC-P**                         | top-left    | **down**    |
| **Windows GDI**, **PDF**, most GUI frameworks | top-left    | **down**    |
| **SVG / PostScript**                          | bottom-left | **up**      |

So we need to **normalize coordinates once**, in the driver layer, so templates can stay consistent (always bottom-left origin, Y up).

---

### 1. Adopt a Canonical Coordinate System

Let’s define the **canonical layout space** used by all templates and JSON emitters:

```
Origin (0,0) = bottom-left corner of label
X increases → right
Y increases ↑ up
Units = mm or dots (converted at runtime)
```

This becomes part of the schema contract.

Any driver that uses a different orientation must invert Y internally.

---

### 2. Add Geometry Context to the Envelope

Extend the JSON envelope slightly to make this explicit and avoid ambiguity later:

```json
{
  "version": "1.0",
  "template": "scleral_v4",
  "dpi": 203,
  "units": "mm",
  "width": 80,
  "height": 60,
  "origin": "bottom-left",     // new
  "y_direction": "up",         // new
  "commands": [ ... ]
}
```

Drivers can then check these keys and decide if they need a coordinate transform.

---

### 3. Implement the Coordinate Conversion

Add a helper in each driver:

#### Python

```python
class PrinterDriver:
    def to_device_coords(self, x: float, y: float, label_height_mm: float) -> tuple[float, float]:
        """Convert canonical (bottom-left, Y-up) to device coords."""
        if self.origin == "top-left":
            # invert Y-axis
            y = label_height_mm - y
        return x, y
```

Then in `move_to()`:

```python
def move_to(self, x, y):
    x_d, y_d = self.to_device_coords(x, y, self.label_height)
    self._send(f"PRPOS {int(x_d)},{int(y_d)}")
```

#### C#

```csharp
public (double X, double Y) ToDeviceCoords(double x, double y, double labelHeight)
{
    if (Origin == "top-left") y = labelHeight - y;
    return (x, y);
}
```

---

### 4. Driver Responsibility Matrix

| Driver    | Origin      | Conversion Needed? | Implementation         |
| --------- | ----------- | ------------------ | ---------------------- |
| PD41      | bottom-left | ❌ none             | direct pass-through    |
| GDI / PDF | top-left    | ✅ invert Y         | `y = label_height - y` |
| ZPL       | top-left    | ✅ invert Y         | same                   |
| SVG / PS  | bottom-left | ❌                  | direct pass-through    |

---

### 5. Benefits

* Templates remain **device-independent** (only one coordinate convention).
* Future renderers (PDF preview, Windows GDI, Linux CUPS, etc.) can be added trivially.
* The schema defines orientation explicitly, so human and machine users can always tell what to expect.

---

### 6. Suggested Schema Addition

Extend `printer_commands.schema.json`:

```json
"origin": { "type": "string", "enum": ["bottom-left", "top-left"], "default": "bottom-left" },
"y_direction": { "type": "string", "enum": ["up", "down"], "default": "up" }
```

---

### ✅ Summary

* Canonicalize on **bottom-left, Y-up** for all templates.
* Drivers handle conversion to their native coordinate system.
* Add `origin` / `y_direction` fields to JSON envelopes.
* Conversion formula: `y_device = label_height - y_canonical` if the driver expects Y down.
