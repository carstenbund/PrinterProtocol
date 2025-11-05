import socket
from printer_protocol import PrinterDriver


class PD41Driver(PrinterDriver):
    """Intermec PD41 driver implementing the PrinterDriver protocol."""

    def __init__(self, host: str, port: int = 9100, dry_run: bool = True):
        self.host, self.port, self.dry_run = host, port, dry_run
        self.sent: list[str] = []
        self.sock: socket.socket | None = None
        self.dpi = 203.0
        
    def __enter__(self):
        if not self.dry_run:
            self.sock = socket.create_connection((self.host, self.port))
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _send(self, line: str) -> None:
        if not line.endswith("\r\n"):
            line += "\r\n"
        if self.dry_run:
            self.sent.append(line.strip())
            return
        assert self.sock is not None
        self.sock.sendall(line.encode("ascii"))

    # ---- Implement protocol ----
    def setup(self, name):
        self._send(f'SETUP "{name}"')

    def set_font(self, name, size):
        self._send(f'FONT "{name}",{int(size)}')

    def set_alignment(self, align):
        self._send(f'ALIGN {align}')

    def set_direction(self, direction):
        self._send(f'DIR {direction}')

    def move_to(self, x, y):
        x_dev, y_dev = self.to_device_coords(x, y)
        self._send(f'PRPOS {int(x_dev)},{int(y_dev)}')

    def draw_text(self, text):
        self._send(f'PRTXT "{text}"')

    def draw_barcode(self, value, type, width, ratio, height, size):
        self._send(f'BARSET "{type}",{width},{ratio},{height},{size}')
        self._send(f'PRBAR "{value}"')

    def comment(self, text):
        self._send(f'REM -- {text} --')

    def print_feed(self):
        self._send("PRINTFEED")

    def get_dpi(self):
        return self.dpi
