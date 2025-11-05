from printer_protocol import PrinterDriver


class GdiDriverStub(PrinterDriver):
    """Mock driver representing a top-left, Y-down coordinate system."""

    def __init__(self) -> None:
        super().__init__()
        self.origin = "top-left"
        self.y_direction = "down"
        self.dpi = 96.0
        self.label_height = 60.0

    def to_device_coords(self, x, y):
        height = self.label_height or 0.0
        if not height:
            return x, y
        return x, height - y

    def setup(self, name):
        print(f"[SETUP] {name}")

    def set_font(self, name, size):
        print(f"[FONT] {name} {size}")

    def set_alignment(self, align):
        print(f"[ALIGN] {align}")

    def set_direction(self, direction):
        print(f"[DIR] {direction}")

    def move_to(self, x, y):
        x_dev, y_dev = self.to_device_coords(x, y)
        print(f"[MOVE] {x_dev:.1f},{y_dev:.1f}")

    def draw_text(self, text):
        print(f"[TEXT] {text}")

    def draw_barcode(self, value, type, width, ratio, height, size):
        print(f"[BARCODE] {type} '{value}' {width}x{height}")

    def comment(self, text):
        print(f"[COMMENT] {text}")

    def print_feed(self):
        print("[PRINTFEED]")

    def get_dpi(self):
        return self.dpi
