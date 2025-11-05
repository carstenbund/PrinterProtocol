from printer_protocol import PrinterDriver


class GdiDriverStub(PrinterDriver):
    """Mock driver simulating graphical output (console only)."""

    device_origin = "top-left"
    device_y_direction = "down"
    dpi = 300.0

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
        print(f"[MOVE] {x_dev},{y_dev}")

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
