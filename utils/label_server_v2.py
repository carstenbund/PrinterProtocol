#!/usr/bin/env python3
"""
Label Server V2
---------------
Catches legacy REGEL$ data, converts to JSON print commands, and renders
them through an abstract printer driver (PD41, GDI, etc).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import socket
import sys
from pathlib import Path
from typing import Dict

# Ensure the shared printer protocol modules are importable when the script
# is executed from the repository root (or utils/ directly).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = PROJECT_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from printer_protocol import JsonCommandInterpreter
from printer_templates import list_templates, render_template
from drivers.pd41_driver import PD41Driver
from drivers.gdi_driver_stub import GdiDriverStub


# ------------------------------------------------------
#  REGEL$ Parser (unchanged from V1)
# ------------------------------------------------------
def parse_regel(regel: str) -> Dict[str, str]:
    regel = regel.strip(" =#&\n\r")
    clean = lambda s: s.strip().replace("\x00", "")
    v: Dict[str, str] = {}

    v["TYPE"] = regel[0:1].strip()
    v["DATUM"] = clean(regel[1:8])
    v["KLANTNR"] = clean(regel[8:12])
    v["BONNR"] = clean(regel[12:19])
    v["REFER"] = clean(regel[19:31])
    v["NAAM"] = clean(regel[31:46])
    v["SUBNAAM"] = clean(regel[46:66])
    v["MATLBL"] = clean(regel[66:70])
    v["MAT"] = clean(regel[70:85])
    v["DKLBL"] = clean(regel[85:89])
    v["DK"] = clean(regel[89:92])
    v["TEKST"] = clean(regel[92:127])
    v["RGT"] = clean(regel[127:129])
    v["CODER"] = clean(regel[129:146])
    v["DIARLBL"] = clean(regel[146:150])
    v["DIAR"] = clean(regel[150:154])
    v["EXCRLBL"] = clean(regel[154:158])
    v["EXCR"] = clean(regel[158:162])
    v["RADRLBL"] = clean(regel[162:166])
    v["RADR"] = clean(regel[166:170])
    v["DPTRLBL"] = clean(regel[170:174])
    v["DPTR"] = clean(regel[174:180])
    v["CYLRLBL"] = clean(regel[180:184])
    v["CYLR"] = clean(regel[184:189])
    v["XASRLBL"] = clean(regel[189:193])
    v["XASR"] = clean(regel[193:196])
    v["SAGRLBL"] = clean(regel[196:200])
    v["SAGR"] = clean(regel[200:205])
    v["PERIFRLBL"] = clean(regel[205:209])
    v["PERIFR"] = clean(regel[209:214])
    v["DRAD2RLBL"] = clean(regel[214:218])
    v["DRAD2R"] = clean(regel[218:222])
    v["IDR"] = clean(regel[222:230])
    v["LFT"] = clean(regel[230:232])
    v["CODEL"] = clean(regel[232:249])
    v["DIALLBL"] = clean(regel[249:253])
    v["DIAL"] = clean(regel[253:257])
    v["EXCLLBL"] = clean(regel[257:261])
    v["EXCL"] = clean(regel[261:265])
    v["RADLLBL"] = clean(regel[265:269])
    v["RADL"] = clean(regel[269:273])
    v["DPTLLBL"] = clean(regel[273:277])
    v["DPTL"] = clean(regel[277:283])
    v["CYLLLBL"] = clean(regel[283:287])
    v["CYLL"] = clean(regel[287:292])
    v["XASLLBL"] = clean(regel[292:296])
    v["XASL"] = clean(regel[296:299])
    v["SAGLLBL"] = clean(regel[299:303])
    v["SAGL"] = clean(regel[303:308])
    v["PERIFLLBL"] = clean(regel[308:312])
    v["PERIFL"] = clean(regel[312:317])
    v["DRAD2LLBL"] = clean(regel[317:321])
    v["DRAD2L"] = clean(regel[321:325])
    v["IDL"] = clean(regel[325:333])
    v["DI"] = clean(regel[333:347])
    v["UDI"] = clean(regel[347:367]) if len(regel) > 367 else ""

    return v


# ------------------------------------------------------
#  CSV logger
# ------------------------------------------------------
def append_csv(parsed: Dict[str, str], path: Path) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=parsed.keys())
        if not exists:
            writer.writeheader()
        writer.writerow(parsed)


def is_valid_regel(data: str) -> bool:
    data = data.strip()
    if not data:
        return False
    if len(data) < 50:
        return False
    if data[0] not in "=#STHMPJKBZ":
        return False
    return True


# ------------------------------------------------------
#  Rendering abstraction (values → JSON commands)
# ------------------------------------------------------
def build_label_commands(values: Dict[str, str], *, template_name: str) -> Dict[str, object]:
    """Render a REGEL$ payload using a registered label template."""

    return render_template(template_name, values)


# ------------------------------------------------------
#  Driver factory
# ------------------------------------------------------
DRIVER_REGISTRY = {
    "pd41": PD41Driver,
    "gdi": GdiDriverStub,
}


def create_driver(name: str, printer_host: str, dry_run: bool) -> object:
    key = name.lower()
    if key not in DRIVER_REGISTRY:
        raise ValueError(f"Unknown driver '{name}'")

    driver_cls = DRIVER_REGISTRY[key]
    if driver_cls is PD41Driver:
        return driver_cls(printer_host, dry_run=dry_run)
    return driver_cls()


# ------------------------------------------------------
#  Core server logic
# ------------------------------------------------------
def run_label_server_v2(
    out_dir: Path,
    printer_host: str,
    *,
    driver_name: str = "pd41",
    template_name: str = "scleral_v4",
    dry_run: bool,
    host: str = "0.0.0.0",
    port: int = 9100,
) -> None:
    print(f"[+] Label server v2 listening on {host}:{port} (driver={driver_name}, dry_run={dry_run})")
    csv_path = out_dir / "labels_v2.csv"
    out_dir.mkdir(parents=True, exist_ok=True)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen()

    try:
        while True:
            conn, addr = srv.accept()
            print(f"[>] Connection from {addr}")
            try:
                data = conn.recv(65535)
                if not data:
                    print("[!] Empty connection — ignored.")
                    conn.close()
                    continue

                text = data.decode("latin-1", errors="ignore").strip()
                if text.endswith("&"):
                    text = text[:-1].strip()

                if not is_valid_regel(text):
                    print("[!] Ignored invalid REGEL$ message")
                    conn.close()
                    continue

                values = parse_regel(text)
                values["RECEIVED_AT"] = datetime.datetime.now().isoformat()
                append_csv(values, csv_path)

                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                print(f"[+] Parsed label TYPE={values.get('TYPE')} len={len(text)}")

                payload = build_label_commands(values, template_name=template_name)
                payload_json = json.dumps(payload, indent=2)

                driver = create_driver(driver_name, printer_host, dry_run=dry_run)
                height = float(payload.get("height", 0.0) or 0.0)
                units = str(payload.get("units", "mm"))
                raw_dpi = payload.get("dpi")
                try:
                    dpi = float(raw_dpi) if raw_dpi is not None else float(driver.get_dpi())
                except (TypeError, ValueError):
                    dpi = float(driver.get_dpi())
                if hasattr(driver, "set_label_context"):
                    driver.set_label_context(height=height, units=units, dpi=dpi)
                interpreter = JsonCommandInterpreter(driver)
                interpreter.run(payload)

                out_file = out_dir / f"label_{ts}.json"
                out_file.write_text(payload_json, encoding="utf-8")
                print(f"[+] JSON envelope saved → {out_file}")

                sent_lines = getattr(driver, "sent", None)
                if sent_lines:
                    out_prn = out_dir / f"label_{ts}.prn"
                    out_prn.write_text("\n".join(sent_lines), encoding="latin-1")
                    print(f"[+] Driver output saved → {out_prn}")

            except Exception as exc:
                print(f"[!] Exception while handling {addr}: {exc}")
            finally:
                conn.close()
                print(f"[<] Closed connection {addr}")
    finally:
        srv.close()


# ------------------------------------------------------
#  CLI entrypoint
# ------------------------------------------------------
def main() -> None:
    templates = list(list_templates())

    parser = argparse.ArgumentParser(
        description="Label Server v2 (REGEL parser + JSON printer protocol)",
    )
    parser.add_argument("--printer", default="200.0.0.118", help="Printer IP address")
    parser.add_argument("--driver", choices=sorted(DRIVER_REGISTRY.keys()), default="pd41", help="Printer driver backend")
    parser.add_argument("--dry", action="store_true", help="Dry run mode (no TCP connection)")
    parser.add_argument("--outdir", default="out_v2", help="Output directory for logs/files")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=9100, help="Listening port")
    if templates:
        parser.add_argument(
            "--template",
            choices=sorted(templates),
            default="scleral_v4",
            help="Label template to use for rendering",
        )
    else:  # pragma: no cover - defensive fallback when no templates registered
        parser.add_argument("--template", default="scleral_v4", help="Label template to use for rendering")
    args = parser.parse_args()

    try:
        run_label_server_v2(
            out_dir=Path(args.outdir),
            printer_host=args.printer,
            driver_name=args.driver,
            template_name=args.template,
            dry_run=args.dry,
            host=args.host,
            port=args.port,
        )
    except KeyboardInterrupt:
        print("\n[!] Stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
