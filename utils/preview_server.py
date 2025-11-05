from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import urllib.parse
import json
import re

class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, directory: str = "out", **kw):
        super().__init__(*a, directory=directory, **kw)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/preview":
            qs = urllib.parse.parse_qs(parsed.query)
            job = qs.get("job", [None])[0]
            if not job:
                self.send_error(400, "Usage: /preview?job=<BONNR or partial>")
                return

            # find matching file(s)
            base_dir = Path(self.directory)
            matches = sorted(base_dir.glob(f"*job*{job}*.html"))
            if not matches:
                self.send_error(404, f"No match for job {job}")
                return

            # serve the last one
            html = matches[-1].read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # fallback: serve static files (index, etc.)
        return super().do_GET()

def start_preview_server(out_dir: Path, host="0.0.0.0", port=8080):
    print(f"[+] Preview server ready on http://{host}:{port}/preview?job=<BONNR>")
    httpd = ThreadingHTTPServer((host, port),
        lambda *a, **kw: PreviewHandler(*a, directory=str(out_dir), **kw))
    httpd.serve_forever()
