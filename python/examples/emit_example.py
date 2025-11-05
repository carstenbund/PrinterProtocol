from pathlib import Path

from printer_protocol import JsonCommandEmitter


em = JsonCommandEmitter("demo_label.xml")
em.set_layout(width=80.0, height=60.0, units="mm", dpi=203.0)
em.emit("Setup", name="TEST_LABEL")
em.emit("SetFont", name="Swiss 721", size=8)
em.emit("MoveTo", x=100, y=50)
em.emit("DrawText", text="Hello JSON World")
em.emit("PrintFeed")
em.validate(Path(__file__).parents[1] / "../printer_commands.schema.json")

out = Path(__file__).parent / "label.json"
out.write_text(em.to_json(), encoding="utf-8")
print(f"Label commands written to {out}")
