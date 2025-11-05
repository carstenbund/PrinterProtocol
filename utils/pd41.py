# pd41.py
from __future__ import annotations
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Protocol

# ---------------------------------------------------------------------------
# Defaults used when upstream systems omit values
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Dict[str, Any]] = {
    "labels": {
        "MATLBL": "MAT",
        "DKLBL": "DK",
        "POSXOFF": 5.0,
    },
    "company": {
        # Default Device Identifier used for UDI generation when none is supplied
        "device_identifier": "08719326771229",
        # Short code printed alongside the company / product details
        "code_short": "CODESH",
    },
}

# ---------------------------
# Transport
# ---------------------------
class PrinterClient:
    def __init__(self, host: str, port: int = 9100, timeout: float = 5.0, dry_run: bool = False):
        self.host, self.port, self.timeout, self.dry_run = host, port, timeout, dry_run
        self._sock: Optional[socket.socket] = None  # type: ignore
        self.sent: List[str] = []
        self._font_name: Optional[str] = None
        self._font_size: Optional[int] = None

    def __enter__(self):
        # Reset printer state tracking whenever a new connection is opened.
        self._font_name = None
        self._font_size = None
        if not self.dry_run:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            self._sock = s
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._sock:
            try: self._sock.shutdown(socket.SHUT_WR)
            except Exception: pass
            self._sock.close()
            self._sock = None

    def send(self, line: str) -> None:
        if not line: return
        if not line.endswith("\r\n"): line += "\r\n"
        if self.dry_run:
            self.sent.append(line.rstrip("\r\n")); return
        if not self._sock:
            raise RuntimeError("PrinterClient not connected. Use context manager.")
        self._sock.sendall(line.encode("utf-8"))

    # FingerPrint convenience
    def font(self, name: str, size: int):
        if self._font_name == name and self._font_size == size:
            return
        self._font_name = name
        self._font_size = size
        self.send(f'FONT "{name}",{size}')
    def dir(self, d: int):               self.send(f"DIR {d}")
    def align(self, a: int):             self.send(f"ALIGN {a}")
    def move_to_position(self, x: float, y: float):
        self.send(f"PRPOS POSX{int(round(x))}%,POSY{int(round(y))}%")
    def print_text(self, text: str, literal: bool = True):
        if literal: self.send(f'PRTXT "{text.replace(chr(34), chr(34)*2)}"')
        else:       self.send(f"PRTXT {text}")
    def barset(self, btype: str, *params: Any):
        self.send(f'BARSET "{btype}",{",".join(map(str, params))}')
    def print_barcode(self, data: str):
        self.send(f'PRBAR "{data.replace(chr(34), chr(34)*2)}"')
    def printfeed(self): self.send("PRINTFEED")

# ---------------------------
# Style & Template protocol
# ---------------------------
@dataclass
class Style:
    font_name: str = "Swiss 721 Bold BT"
    size_name: int = 8
    size_sub: int = 7
    size_label: int = 7
    size_value: int = 6
    size_small: int = 5
    size_box_title: int = 10
    dir_normal: int = 1
    dir_rotated: int = 3
    dir_flipped: int = 4
    align_left: int = 1
    align_center: int = 4
    align_right: int = 6
    align_mid: int = 5
    align_top: int = 7
    align_bottom: int = 3

class LabelTemplate(Protocol):
    def compute_fields(self, values: Dict[str, Any]) -> Dict[str, str]: ...
    def render(self, values: Dict[str, Any], client: PrinterClient, style: Style) -> None: ...

# ---------------------------
# Domain (common terms)
# ---------------------------
@dataclass
class LensSpec:
    product_code: str
    code_full: Optional[str] = None
    diameter_mm: Optional[float] = None
    overall_diameter_mm: Optional[float] = None
    base_curve_mm: Optional[float] = None
    sagittal_mm: Optional[float] = None
    sphere_d: Optional[float] = None
    cylinder_d: Optional[float] = None
    axis_deg: Optional[int] = None
    peripheral: Optional[str] = None
    type_desc: Optional[str] = None
    material: Optional[str] = None
    dk: Optional[str] = None
    execution: Optional[str] = None
    notes: Optional[str] = None
    scleral_aperture: Optional[str] = None  # N/W/X
    scleral_edge: Optional[str] = None      # N/s/S/f/F
    toric_ring: Optional[str] = None        # "0.50","1.00","1.50","0.75"

@dataclass
class OrderSpec:
    order_number: str
    customer_code: str
    patient_name: str
    expiry_yymmdd: str
    device_identifier: Optional[str] = None
    right: Optional[LensSpec] = None
    left: Optional[LensSpec] = None
    reference: Optional[str] = None
    code_short: Optional[str] = None
    id_right: Optional[str] = None
    id_left: Optional[str] = None

# ---------------------------
# Helpers
# ---------------------------
def left(s: str, n: int) -> str:  return s[:n]
def right(s: str, n: int) -> str: return s[-n:] if n > 0 else ""
def trim_right_spaces(s: str) -> str: return s.rstrip(" ")
def fmt_num(x: Optional[float], places: int = 2) -> str:
    if x is None: return ""
    s = f"{x:.{places}f}";  return s.rstrip("0").rstrip(".") if "." in s else s
def sign_power(x: Optional[float]) -> str:
    if x is None: return ""
    s = f"{x:+.2f}"; return s.rstrip("0").rstrip(".")
def _normalize_gs1_date(expiry: str) -> str:
    """Return YYMMDD from GS1 expiry input (accepts YYMMDD or YYYYMMDD)."""
    digits = "".join(ch for ch in (expiry or "") if ch.isdigit())
    if len(digits) >= 8:
        digits = digits[-8:]
    if len(digits) == 8:
        digits = digits[2:]
    return digits


def udi_string(di: str, exp_yymmdd: str, lot: str) -> str:
    di_clean = (di or "").strip()
    exp_clean = _normalize_gs1_date(exp_yymmdd)
    lot_clean = (lot or "").strip()
    return f"(01){di_clean}(17){exp_clean}(10){lot_clean}"
def edge_suffix_for(code_prefix: str, drad2: Optional[str]) -> str:
    if code_prefix.startswith("7M"): return {"0.75": " T1","1.50":" T2"}.get(drad2 or "", "")
    if code_prefix.startswith("7T"): return {"0.50": " T1","1.00":" T2","1.50":" T3"}.get(drad2 or "", "")
    return ""
def is_blank_or_zero(s: str) -> bool:
    t = (s or "").strip()
    if not t: return True
    try: return float(t) == 0.0
    except: return False

# ---------------------------
# Template: Scleral
# ---------------------------
class ScleralLabelTemplate:
    def compute_fields(self, v: Dict[str, Any]) -> Dict[str, str]:
        # pull minimal set; defaults ok
        SUBNAAM = str(v.get("SUBNAAM", ""))
        CODER   = str(v.get("CODER", ""))
        CODEL   = str(v.get("CODEL", ""))
        SCLAPTR = str(v.get("SCLAPTR", ""))
        SCLAPTL = str(v.get("SCLAPTL", ""))
        SCLEDGR = str(v.get("SCLEDGR", ""))
        SCLEDGL = str(v.get("SCLEDGL", ""))
        DRAD2R  = str(v.get("DRAD2R", ""))
        DRAD2L  = str(v.get("DRAD2L", ""))
        CYLR    = str(v.get("CYLR", " "))
        CYLL    = str(v.get("CYLL", " "))
        XASR    = str(v.get("XASR", ""))
        XASL    = str(v.get("XASL", ""))
        BONNR   = str(v.get("BONNR", ""))
        DI      = str(v.get("DI", ""))
        DATUM   = str(v.get("DATUM", ""))
        UDI     = str(v.get("UDI", ""))

        def apt(code3, apt): 
            return {"N":"","W":"Wide ","X":"Extra Wide "}.get(apt, "") if code3=="7MS" else ""
        def edge(code3, e):
            return {"N":"","s":"s1","S":"s2","f":"f1","F":"f2"}.get(e,"") if code3=="7MS" else ""

        SUBNAAM_trim = trim_right_spaces(SUBNAAM)
        SUBNAAMR = SUBNAAM_trim
        SUBNAAML = SUBNAAM_trim
        if left(CODER,3)=="7MS": SUBNAAMR = apt("7MS",SCLAPTR)+edge("7MS",SCLEDGR)
        if left(CODEL,3)=="7MS": SUBNAAML = apt("7MS",SCLAPTL)+edge("7MS",SCLEDGL)

        # T1/T2/T3 suffixes
        if left(CODER,2) in ("7M","7T"): SUBNAAMR = SUBNAAM_trim + edge_suffix_for(left(CODER,2), DRAD2R)
        if left(CODEL,2) in ("7M","7T"): SUBNAAML = SUBNAAM_trim + edge_suffix_for(left(CODEL,2), DRAD2L)

        CYLASR = "" if right(CYLR,1)==" " else f"/{CYLR}x{XASR}"
        CYLASL = "" if right(CYLL,1)==" " else f"/{CYLL}x{XASL}"

        show_right = not is_blank_or_zero(CODER)
        show_left  = not is_blank_or_zero(CODEL)

        out = dict(v)  # keep all existing fields
        if not UDI.strip() and any(part.strip() for part in (DI, DATUM, BONNR)):
            UDI = udi_string(DI, DATUM, BONNR)
        out.update({
            "SUBNAAMR": SUBNAAMR, "SUBNAAML": SUBNAAML,
            "CYLASR": CYLASR, "CYLASL": CYLASL,
            "_show_right": "1" if show_right else "0",
            "_show_left":  "1" if show_left  else "0",
            "UDI": UDI,
        })
        return {k: ("" if v is None else v) for k,v in out.items()}

    def pos(self, x: float, y: float, xoff: float = 0.0) -> Tuple[float,float]:
        return x + xoff, y

    def render(self, values: Dict[str, Any], client: PrinterClient, style: Style) -> None:
        print("wrong renderer used")
        return
        f = self.compute_fields(values); xoff = float(values.get("POSXOFF", 0.0))

        # RIGHT
        if f["_show_right"]=="1":
            client.font(style.font_name, style.size_name); client.dir(style.dir_normal); client.align(style.align_mid)
            client.move_to_position(*self.pos(8,6)); client.print_text(f["NAAM"])
            client.font(style.font_name, style.size_sub); client.align(style.align_center)
            client.move_to_position(*self.pos(6,5)); client.print_text(f["SUBNAAMR"])
            client.move_to_position(*self.pos(6,4)); client.print_text(f.get("SAGRLBL","SAG"))
            client.move_to_position(*self.pos(6,3)); client.print_text(f.get("RADRLBL","RAD"))
            client.move_to_position(*self.pos(6,2)); client.print_text(f.get("DPTRLBL","DPT"))
            client.move_to_position(*self.pos(8,4)); client.print_text(f.get("DIARLBL","DIA"))
            client.move_to_position(*self.pos(8,3)); client.print_text(f.get("PERIFRLBL","PERIF"))
            client.font(style.font_name, style.size_value); client.align(style.align_right)
            client.move_to_position(*self.pos(8,4)); client.print_text(f.get("SAGR",""))
            client.move_to_position(*self.pos(8,3)); client.print_text(f.get("RADR",""))
            client.move_to_position(*self.pos(9,2)); client.print_text(f.get("DPTR",""))
            client.font(style.font_name, style.size_value); client.align(style.align_center)
            client.move_to_position(*self.pos(9,2)); client.print_text(f.get("CYLASR",""))
            client.font(style.font_name, style.size_value); client.align(style.align_right)
            client.move_to_position(*self.pos(11,4)); client.print_text(f.get("DIAR",""))
            client.move_to_position(*self.pos(11,3)); client.print_text(f.get("PERIFR",""))
            client.font(style.font_name, style.size_small); client.align(style.align_center)
            client.move_to_position(*self.pos(7,1)); client.print_text(f.get("BONNR",""))
            if right(f.get("DATUM"," "),1)!=" ":
                client.move_to_position(*self.pos(10,1)); client.print_text("EXP "+f["DATUM"])
            client.font(style.font_name, style.size_sub); client.align(style.align_right)
            client.move_to_position(*self.pos(11,5)); client.print_text(f.get("RGT","R"))
            client.font(style.font_name, style.size_sub); client.dir(style.dir_rotated); client.align(style.align_left)
            client.move_to_position(*self.pos(11,12)); client.print_text(f.get("IDR",""))

        # LEFT
        if f["_show_left"]=="1":
            client.font(style.font_name, style.size_name); client.dir(style.dir_normal); client.align(style.align_mid)
            client.move_to_position(*self.pos(8+xoff,6)); client.print_text(f["NAAM"])
            client.font(style.font_name, style.size_sub); client.align(style.align_center)
            client.move_to_position(*self.pos(6+xoff,5)); client.print_text(f["SUBNAAML"])
            client.move_to_position(*self.pos(6+xoff,4)); client.print_text(f.get("SAGLLBL","SAG"))
            client.move_to_position(*self.pos(6+xoff,3)); client.print_text(f.get("RADLLBL","RAD"))
            client.move_to_position(*self.pos(6+xoff,2)); client.print_text(f.get("DPTLLBL","DPT"))
            client.move_to_position(*self.pos(8+xoff,4)); client.print_text(f.get("DIALLBL","DIA"))
            client.move_to_position(*self.pos(8+xoff,3)); client.print_text(f.get("PERIFLLBL","PERIF"))
            client.font(style.font_name, style.size_value); client.align(style.align_right)
            client.move_to_position(*self.pos(8+xoff,4)); client.print_text(f.get("SAGL",""))
            client.move_to_position(*self.pos(8+xoff,3)); client.print_text(f.get("RADL",""))
            client.move_to_position(*self.pos(9+xoff,2)); client.print_text(f.get("DPTL",""))
            client.font(style.font_name, style.size_value); client.align(style.align_center)
            client.move_to_position(*self.pos(9+xoff,2)); client.print_text(f.get("CYLASL",""))
            client.font(style.font_name, style.size_value); client.align(style.align_right)
            client.move_to_position(*self.pos(11+xoff,4)); client.print_text(f.get("DIAL",""))
            client.move_to_position(*self.pos(11+xoff,3)); client.print_text(f.get("PERIFL",""))
            client.font(style.font_name, style.size_small); client.align(style.align_center)
            client.move_to_position(*self.pos(7+xoff,1)); client.print_text(f.get("BONNR",""))
            if right(f.get("DATUM"," "),1)!=" ":
                client.move_to_position(*self.pos(10+xoff,1)); client.print_text("EXP "+f["DATUM"])
            client.font(style.font_name, style.size_sub); client.align(style.align_right)
            client.move_to_position(*self.pos(11+xoff,5)); client.print_text(f.get("LFT","L"))
            client.font(style.font_name, style.size_sub); client.dir(style.dir_rotated); client.align(style.align_left)
            client.move_to_position(*self.pos(11+xoff,12)); client.print_text(f.get("IDL",""))

        # BOX / UDI
        client.font(style.font_name, style.size_box_title); client.dir(style.dir_flipped); client.align(style.align_top)
        client.move_to_position(*self.pos(0,0)); client.print_text(f.get("CODESH","") + " " + f.get("NAAM",""))
        client.font(style.font_name, style.size_box_title); client.dir(style.dir_flipped); client.align(style.align_center)
        if f["_show_right"]=="1": client.move_to_position(*self.pos(1,10)); client.print_text(f.get("RGT","R"))
        if f["_show_left"]=="1":  client.move_to_position(*self.pos(1,9));  client.print_text(f.get("LFT","L"))
        client.font(style.font_name, style.size_sub); client.dir(style.dir_flipped); client.align(style.align_left)
        client.move_to_position(*self.pos(2,0)); client.print_text(f.get("REFER",""))
        client.font(style.font_name, style.size_sub); client.dir(style.dir_flipped); client.align(style.align_right)
        client.move_to_position(*self.pos(2,11)); client.print_text(f.get("KLANTNR",""))
        client.dir(style.dir_flipped); client.align(style.align_top)
        client.move_to_position(*self.pos(3,0)); client.barset("DATAMATRIX",2,1,3,100)
        client.print_barcode(f.get("UDI",""))
        client.font(style.font_name, style.size_sub); client.dir(style.dir_flipped); client.align(style.align_right)
        client.move_to_position(*self.pos(3,13)); client.print_text("UDI-DI(01)")
        client.move_to_position(*self.pos(4,13)); client.print_text("EXP(17)")
        client.move_to_position(*self.pos(5,13)); client.print_text("LOT(10)")
        client.font(style.font_name, style.size_sub); client.dir(style.dir_flipped); client.align(style.align_center)
        client.move_to_position(*self.pos(3,14)); client.print_text(f.get("DI",""))
        client.move_to_position(*self.pos(4,14)); client.print_text(f.get("DATUM",""))
        client.move_to_position(*self.pos(5,14)); client.print_text(f.get("BONNR",""))
        client.font(style.font_name, style.size_sub); client.dir(style.dir_flipped); client.align(style.align_center)
        client.move_to_position(*self.pos(3,15)); client.print_text(f.get("MATLBL","MAT"))
        client.move_to_position(*self.pos(5,15)); client.print_text(f.get("DKLBL","DK"))
        client.font(style.font_name, style.size_value); client.dir(style.dir_flipped); client.align(style.align_center)
        client.move_to_position(*self.pos(4,15)); client.print_text(f.get("MAT",""))
        client.font(style.font_name, style.size_value); client.dir(style.dir_flipped); client.align(style.align_right)
        client.move_to_position(*self.pos(5,11)); client.print_text(f.get("DK",""))
        client.printfeed()

# ---------------------------
# Builder
# ---------------------------
@dataclass
class LabelBuilder:
    templates: Dict[str, LabelTemplate] = field(default_factory=lambda: {"scleral": ScleralLabelTemplate()})
    styles: Dict[str, Style] = field(default_factory=lambda: {"default": Style()})
    def render(self, template: str, values: Dict[str, Any], client: PrinterClient, style_name: str="default") -> None:
        t = self.templates.get(template);  s = self.styles.get(style_name)
        if not t: raise KeyError(f"Unknown template: {template}")
        if not s: raise KeyError(f"Unknown style: {style_name}")
        t.render(values, client, s)

# ---------------------------
# Common→Template mapping + pretend feeder
# ---------------------------
def build_side_values(side: str, lens: LensSpec) -> Dict[str, Any]:
    px = "R" if side=="R" else "L"
    code = lens.product_code or ""
    base_sub = (lens.type_desc or "").strip()
    apt = {"N":"","W":"Wide ","X":"Extra Wide "}.get((lens.scleral_aperture or "").upper(),"")
    edge_code = {"N":"","s":"s1","S":"s2","f":"f1","F":"f2"}.get((lens.scleral_edge or ""), "")
    sub_7ms = (apt + edge_code) if code.startswith("7MS") else None
    sub = (sub_7ms if sub_7ms is not None else base_sub).rstrip()
    sub += edge_suffix_for(code[:2], lens.toric_ring)
    cyl = sign_power(lens.cylinder_d)
    cyla = f"/{cyl}x{lens.axis_deg}" if cyl and lens.axis_deg is not None else ""
    return {
        ("CODER" if side=="R" else "CODEL"): code,
        "SUBNAAM": base_sub,
        ("SUBNAAMR" if side=="R" else "SUBNAAML"): sub,
        ("CYLASR" if side=="R" else "CYLASL"): cyla,
        ( "SAGRLBL" if side=="R" else "SAGLLBL"): "SAG",
        ( "RADRLBL" if side=="R" else "RADLLBL"): "RAD",
        ( "DPTRLBL" if side=="R" else "DPTLLBL"): "DPT",
        ( "DIARLBL" if side=="R" else "DIALLBL"): "DIA",
        ("PERIFRLBL" if side=="R" else "PERIFLLBL"): "PERIF",
        ("SAGR" if side=="R" else "SAGL"): fmt_num(lens.sagittal_mm, 3),
        ("RADR" if side=="R" else "RADL"): fmt_num(lens.base_curve_mm, 2),
        ("DPTR" if side=="R" else "DPTL"): sign_power(lens.sphere_d),
        ("DIAR" if side=="R" else "DIAL"): fmt_num(lens.overall_diameter_mm or lens.diameter_mm, 2),
        ("PERIFR" if side=="R" else "PERIFL"): lens.peripheral or "",
        ("RGT" if side=="R" else "LFT"): ("R" if side=="R" else "L"),
        ("IDR" if side=="R" else "IDL"): "",
    }

def build_values_from_order(order: OrderSpec) -> Dict[str, Any]:
    label_defaults = DEFAULTS.get("labels", {})
    company_defaults = DEFAULTS.get("company", {})
    device_identifier = order.device_identifier or company_defaults.get("device_identifier", "")
    code_short = order.code_short or company_defaults.get("code_short", "")

    out: Dict[str, Any] = {
        "NAAM": order.patient_name,
        "BONNR": order.order_number,
        "KLANTNR": order.customer_code,
        "DATUM": order.expiry_yymmdd,
        "DI": device_identifier,
        "CODESH": code_short,
        "REFER": order.reference or "",
        "MATLBL": label_defaults.get("MATLBL", "MAT"),
        "DKLBL": label_defaults.get("DKLBL", "DK"),
        "MAT": "", "DK": "",
        "UDI": udi_string(device_identifier, order.expiry_yymmdd, order.order_number),
        "POSXOFF": float(label_defaults.get("POSXOFF", 0.0)),
        "CODER": "", "CODEL": "",
    }
    if order.right:
        out.update(build_side_values("R", order.right))
        out["IDR"] = order.id_right or out.get("IDR","")
        out["MAT"] = order.right.material or out["MAT"]
        out["DK"]  = order.right.dk or out["DK"]
    if order.left:
        out.update(build_side_values("L", order.left))
        out["IDL"] = order.id_left or out.get("IDL","")
    return out

def pretend_feeder() -> OrderSpec:
    company_defaults = DEFAULTS.get("company", {})
    common = dict(
        diameter_mm=13.00, overall_diameter_mm=17.5, base_curve_mm=7.80,
        sagittal_mm=3.875, sphere_d=+2.00, cylinder_d=-1.00, axis_deg=10,
        material="Optimum Extreme", dk="125", type_desc="mini MISA TFT",
        execution="TFT Wide", peripheral="Std",
    )
    right = LensSpec(product_code="7MG", code_full="7MG&4V64C00840ACV",
                     scleral_aperture="W", scleral_edge="S", toric_ring="0.75", **common)
    left  = LensSpec(product_code="7MG", code_full="7MG&4V64C00840ACV",
                     scleral_aperture="W", scleral_edge="f", toric_ring="0.75", **common)
    return OrderSpec(
        order_number="1008018", customer_code="1250",
        patient_name="MICROLENS", expiry_yymmdd="261231",
        device_identifier=company_defaults.get("device_identifier", "08719326771229"),
        right=right, left=left, reference="TL03 / TL04",
        code_short=company_defaults.get("code_short", "CODESH"), id_right="TL03", id_left="TL04",
    )

# Public API
__all__ = [
    "PrinterClient", "Style", "LabelTemplate", "ScleralLabelTemplate",
    "LabelBuilder", "LensSpec", "OrderSpec",
    "build_values_from_order", "pretend_feeder",
]

