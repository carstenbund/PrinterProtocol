import socket
import select
import datetime
import csv
import argparse
import sys
from pathlib import Path

# Real printer + rendering infrastructure
from pd41 import PrinterClient, LabelBuilder
from xml_template import XMLLabelTemplate


# ------------------------------------------------------
#  REGEL$ Parser (based on your BASIC mapping)
# ------------------------------------------------------
def parse_regel(regel: str) -> dict:
    regel = regel.strip(" =#&\n\r")
    clean = lambda s: s.strip().replace("\x00", "")
    v = {}

    # Core identification fields
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
def append_csv(parsed: dict, path: Path):
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=parsed.keys())
        if not exists:
            w.writeheader()
        w.writerow(parsed)

def is_valid_regel(data: str) -> bool:
    """Quick sanity check before parsing."""
    data = data.strip()
    if not data:
        return False
    if len(data) < 50:  # too short to contain required fields
        return False
    if data[0] not in "=#STHMPJKBZ":
        return False
    return True


def run_label_server(
    template_path: Path,
    out_dir: Path,
    printer_host: str,
    dry_run: bool,
    host: str = "0.0.0.0",
    port: int = 9100,
):
    print(f"[+] Label server listening on {host}:{port}")
    csv_path = out_dir / "labels.csv"
    out_dir.mkdir(parents=True, exist_ok=True)

    xml_template = XMLLabelTemplate(str(template_path))
    builder = LabelBuilder()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen()

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

            if not text or len(text) < 80:
                print("[!] Ignored: too short or empty.")
                conn.close()
                continue
            if not (text.startswith("=#") or text.startswith("=") or text[0].isalpha()):
                print("[!] Ignored: does not start with expected =#/=")
                conn.close()
                continue

            # Valid REGEL$ detected
            values = parse_regel(text)
            values["RECEIVED_AT"] = datetime.datetime.now().isoformat()
            append_csv(values, csv_path)

            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"[+] Parsed single label TYPE={values.get('TYPE')} len={len(text)}")

            try:
                with PrinterClient(printer_host, dry_run=dry_run) as client:
                    xml_template.render(values, client)
                    out_file = out_dir / f"label_{ts}.prn"
                    out_file.write_text("\n".join(client.sent), encoding="latin-1")
                    print(f"[+] Rendered and saved → {out_file}")
            except Exception as e:
                print(f"[!] Render error: {e}")
                (out_dir / f"error_{ts}.log").write_text(str(e))

        except Exception as e:
            print(f"[!] Exception while handling {addr}: {e}")
        finally:
            conn.close()
            print(f"[<] Closed connection {addr}")


# ------------------------------------------------------
#  CLI entrypoint
# ------------------------------------------------------

import threading
from preview_server import start_preview_server

def main():
    parser = argparse.ArgumentParser(description="Label Print Server (REGEL parser + PD41 printer)")
    parser.add_argument("--template", required=True, help="Path to XML label template")
    parser.add_argument("--printer", default="200.0.0.118", help="Printer IP")
    parser.add_argument("--dry", action="store_true", help="Dry run (no actual print)")
    parser.add_argument("--outdir", default="out", help="Output directory for logs/files")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=9100, help="Listening port")
    parser.add_argument("--preview", action="store_true", help="Start preview server on port 8080")
    parser.add_argument("--preview-port", type=int, default=8080, help="Preview server port")
    args = parser.parse_args()

    # ----------------------------------------------------
    # optional preview server
    # ----------------------------------------------------
    if args.preview:
        threading.Thread(
            target=start_preview_server,
            args=(Path(args.outdir),),
            kwargs={"host": "0.0.0.0", "port": args.preview_port},
            daemon=True,
        ).start()

    try:
        run_label_server(
            template_path=Path(args.template),
            out_dir=Path(args.outdir),
            printer_host=args.printer,
            dry_run=args.dry,
            host=args.host,
            port=args.port,
        )
    except KeyboardInterrupt:
        print("\n[!] Stopped by user.")
        sys.exit(0)



if __name__ == "__main__":
    main()

