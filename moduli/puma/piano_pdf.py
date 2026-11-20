"""Generazione PDF del Piano di Sicurezza (reportlab incluso in vendor/, nessuna installazione; senza Pillow).
Pagine: 1 riepilogo+mappa (funzionario di guardia) · 2 vuota · 3 riepilogo+mappa (SO) · 4 organizzazione · 5 matrice di rischio
· 6 schema ICS · 7.. fogli firme.  Versione ridotta: 3, 4 + fogli firme.  Allegato a parte: manovre della specializzazione."""
import io, math, os, struct, sys, zlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vendor"))   # versione inclusa e collaudata (patchata per funzionare senza Pillow)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.graphics.charts.spider import SpiderChart
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

W, H = A4
M = 36
ROSSO, ANTRACITE, GIALLO, GRIGIO = colors.HexColor("#B71C1C"), colors.HexColor("#212121"), colors.HexColor("#FBC02D"), colors.HexColor("#E0E0E0")
VERDE = colors.HexColor("#2E7D32")
LIV_COL = {"BASSO": colors.HexColor("#2E7D32"), "MEDIO": colors.HexColor("#F9A825"), "ALTO": colors.HexColor("#E65100"), "CRITICO": colors.HexColor("#B71C1C")}


# ---------- pittogrammi meteo (codici WMO di Open-Meteo) ----------
def categoria(code):
    c = int(code)
    if c == 0: return "sole"
    if c == 1: return "poco"
    if c == 2: return "parz"
    if c == 3: return "coperto"
    if c in (45, 48): return "nebbia"
    if c in (71, 73, 75, 77, 85, 86): return "neve"
    if c >= 95: return "temporale"
    return "pioggia"          # 51-67 e 80-82: pioggerella, pioggia, rovesci

def icona(cat, w=26, h=20):
    """Pittogramma vettoriale (Drawing) per la categoria meteo."""
    from reportlab.graphics.shapes import Circle, Rect, Line, Polygon, Group
    d = Drawing(w, h); GRAY, SUN, BLU = colors.HexColor("#78909C"), colors.HexColor("#F9A825"), colors.HexColor("#1565C0")
    def sole(cx, cy, r):
        for k in range(8):
            a = math.radians(k * 45); d.add(Line(cx + math.cos(a) * (r + 1.5), cy + math.sin(a) * (r + 1.5), cx + math.cos(a) * (r + 4), cy + math.sin(a) * (r + 4), strokeColor=SUN, strokeWidth=1.2))
        d.add(Circle(cx, cy, r, fillColor=SUN, strokeColor=SUN))
    def nuvola(dx=0, dy=0, col=GRAY):
        for cx, cy, r in ((8, 8, 4), (13, 11, 5.5), (18, 8, 4)): d.add(Circle(cx + dx, cy + dy, r, fillColor=col, strokeColor=col))
        d.add(Rect(8 + dx, 4 + dy, 10, 5, fillColor=col, strokeColor=col))
    if cat == "sole": sole(w / 2, h / 2, 4.5)
    elif cat == "poco": sole(8, 13, 3.5); nuvola(3, -3)
    elif cat == "parz": sole(7, 14, 3); nuvola(1, -2)
    elif cat == "coperto": nuvola(0, 2)
    elif cat == "nebbia":
        for k in range(4): d.add(Line(3, 3 + k * 4.5, 23, 3 + k * 4.5, strokeColor=GRAY, strokeWidth=1.6))
    elif cat == "pioggia":
        nuvola(0, 5)
        for x in (8, 13, 18): d.add(Line(x, 6, x - 2, 1, strokeColor=BLU, strokeWidth=1.3))
    elif cat == "neve":
        nuvola(0, 5)
        for x in (8, 13, 18): d.add(Circle(x, 3, 1.4, fillColor=colors.HexColor("#4FC3F7"), strokeColor=colors.HexColor("#0288D1")))
    else:
        nuvola(0, 5, colors.HexColor("#455A64")); d.add(Polygon([14, 8, 10, 2, 13, 2, 11, -2, 17, 5, 14, 5], fillColor=SUN, strokeColor=colors.HexColor("#E65100"), strokeWidth=.5))
    return d

def _simbolo(c, kind, X, Y, r=7):
    """Pallino rosso = area addestramento · cerchio verde con H = RV elicottero · cerchio verde con croce = RV ambulanza."""
    c.saveState(); c.setStrokeColor(colors.white); c.setLineWidth(2); c.setFillColor(ROSSO if kind == "area" else VERDE); c.circle(X, Y, r, fill=1)
    c.setFillColor(colors.white)
    if kind == "h": c.setFont("Helvetica-Bold", r * 1.5); c.drawCentredString(X, Y - r * 0.52, "H")
    elif kind == "amb": c.rect(X - r * .6, Y - r * .18, r * 1.2, r * .36, fill=1, stroke=0); c.rect(X - r * .18, Y - r * .6, r * .36, r * 1.2, fill=1, stroke=0)
    c.restoreState()

def _legenda(c, x, y):
    """Legenda dei simboli della mappa (riga alta 18 pt con base in y)."""
    c.saveState(); c.setStrokeColor(colors.grey); c.setLineWidth(.5); c.rect(x, y, W - 2 * M, 18)
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(ANTRACITE); c.drawString(x + 6, y + 6, "LEGENDA")
    for X, k, t in ((x + 85, "area", "Area addestramento"), (x + 215, "h", "RV elicottero"), (x + 330, "amb", "RV ambulanza")):
        _simbolo(c, k, X, y + 9, 6); c.setFont("Helvetica", 8); c.setFillColor(ANTRACITE); c.drawString(X + 10, y + 6, t)
    c.restoreState()

# ---------- PNG -> RGB in puro Python (le tile della mappa) ----------
class PngReader(ImageReader):
    def __init__(self, data):
        self._ident = None; self.fileName = "tile"; self._image = None; self._dataA = None
        self._w, self._h, self._rgb = _decode_png(data)
        self.mode = "RGB"; self._transparent = None
    def getSize(self): return self._w, self._h
    def getRGBData(self): return self._rgb
    def getTransparent(self): return None
    def jpeg_fh(self): return None
    def identity(self): return "png%d" % id(self)

def _decode_png(b):
    if b[:8] != b"\x89PNG\r\n\x1a\n": raise ValueError("non è un PNG")
    pos, idat, plte = 8, [], None
    while pos < len(b):
        n, t = struct.unpack(">I4s", b[pos:pos + 8]); body = b[pos + 8:pos + 8 + n]; pos += 12 + n
        if t == b"IHDR": w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif t == b"PLTE": plte = body
        elif t == b"IDAT": idat.append(body)
    if depth != 8 or interlace or ctype not in (0, 2, 3, 4, 6): raise ValueError("PNG non supportato")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]; stride = w * bpp
    raw = zlib.decompress(b"".join(idat)); out = bytearray(); prev = bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]; row = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(bpp, stride): row[i] = (row[i] + row[i - bpp]) & 255
        elif f == 2:
            for i in range(stride): row[i] = (row[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride): row[i] = (row[i] + ((row[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0; c_ = prev[i - bpp] if i >= bpp else 0; p = a + prev[i] - c_
                pa, pb, pc = abs(p - a), abs(p - prev[i]), abs(p - c_)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else prev[i] if pb <= pc else c_)) & 255
        out += row; prev = row
    rgb = bytearray()
    for y in range(h):
        r = out[y * stride:(y + 1) * stride]
        if ctype == 2: rgb += r
        elif ctype == 6:
            for i in range(0, stride, 4): rgb += r[i:i + 3]
        elif ctype == 3:
            for v in r: rgb += plte[v * 3:v * 3 + 3]
        else:
            for i in range(0, stride, bpp): rgb += bytes((r[i],)) * 3
    return w, h, bytes(rgb)


# ---------- mappa statica da tile ----------
def _px(lat, lon, z):
    n = 256 * 2 ** z; s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n

def mappa(c, x, y, w, h, area, rv, amb, tile_fn):
    """Disegna in (x,y,w,h) una mappa con segnaposto area (rosso) e RV (giallo). area/rv = (lat,lon) o None."""
    c.saveState(); c.setStrokeColor(ANTRACITE); c.setFillColor(GRIGIO); c.rect(x, y, w, h, fill=1)
    if not area:
        c.setFillColor(ANTRACITE); c.setFont("Helvetica", 9); c.drawCentredString(x + w / 2, y + h / 2, "Coordinate non impostate"); c.restoreState(); return
    pts = [p for p in (area, rv, amb) if p]; z = 8
    for zz in range(17, 7, -1):
        ps = [_px(p[0], p[1], zz) for p in pts]
        if max(p[0] for p in ps) - min(p[0] for p in ps) < w - 70 and max(p[1] for p in ps) - min(p[1] for p in ps) < h - 70: z = zz; break
    ps = [_px(p[0], p[1], z) for p in pts]; cx = (max(p[0] for p in ps) + min(p[0] for p in ps)) / 2; cy = (max(p[1] for p in ps) + min(p[1] for p in ps)) / 2
    p = c.beginPath(); p.rect(x, y, w, h); c.clipPath(p, stroke=0, fill=0)
    left, top = cx - w / 2, cy - h / 2
    for tx in range(int(left // 256), int((left + w) // 256) + 1):
        for ty in range(int(top // 256), int((top + h) // 256) + 1):
            if not (0 <= tx < 2 ** z and 0 <= ty < 2 ** z): continue
            try: data = tile_fn(z, tx, ty); img = PngReader(data) if data else None
            except Exception: img = None
            X, Y = x + tx * 256 - left, y + h - ((ty + 1) * 256 - top)
            if img: c.drawImage(img, X, Y, 256, 256)
            else:
                c.setFillColor(colors.HexColor("#EEEEEE")); c.rect(X, Y, 256, 256, stroke=0, fill=1); c.setFillColor(colors.grey); c.setFont("Helvetica", 7)
                c.drawString(X + 6, Y + 128, "mappa non disponibile (tile non scaricata)")
    def marker(pt, kind, lab):
        px, py = _px(pt[0], pt[1], z); X, Y = x + px - left, y + h - (py - top)
        _simbolo(c, kind, X, Y, 8); c.setFillColor(ANTRACITE); c.setFont("Helvetica-Bold", 8); c.drawString(X + 11, Y - 3, lab)
    marker(area, "area", "AREA"); rv and marker(rv, "h", "RV ELICOTTERO"); amb and marker(amb, "amb", "RV AMBULANZA")
    c.restoreState(); c.setFont("Helvetica", 6); c.setFillColor(colors.grey); c.drawRightString(x + w - 2, y + 2, "© OpenStreetMap contributors")


# ---------- elementi comuni ----------
def _fmt(v): return "" if v is None else str(v)

def _testata(c, d, titolo, n):
    c.setFillColor(ROSSO); c.rect(0, H - 56, W, 56, stroke=0, fill=1); c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14); c.drawString(M, H - 27, titolo); c.setFont("Helvetica", 8)
    c.drawString(M, H - 45, "P.U.M.A. – Piattaforma Unificata Monitoraggio Addestramenti"); c.setFont("Helvetica-Bold", 12); c.drawRightString(W - M, H - 45, d["cod_add"])
    c.setFillColor(colors.grey); c.setFont("Helvetica", 7); c.drawString(M, 20, f"{d['cod_add']} – generato il {d['generato']}"); c.drawRightString(W - M, 20, f"pag. {n}")
    c.setFillColor(ANTRACITE)

def _righe(c, x, y, righe, wl=110, wt=400, size=9):
    for k, v in righe:
        lines = simpleSplit(_fmt(v) or "—", "Helvetica", size, wt)
        c.setFont("Helvetica-Bold", size); c.drawString(x, y, k); c.setFont("Helvetica", size)
        for ln in lines: c.drawString(x + wl, y, ln); y -= size + 3
        y -= 2
    return y

def _tabella(c, data, widths, x, y_top, size=8, head=True, extra=None):
    t = Table([[Paragraph(_fmt(v), ParagraphStyle("t", fontName="Helvetica", fontSize=size, leading=size + 2)) if isinstance(v, str) else v for v in r] for r in data], colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if head: st += [("BACKGROUND", (0, 0), (-1, 0), GRIGIO)]
    t.setStyle(TableStyle(st + (extra or []))); w, h = t.wrapOn(c, sum(widths), H); t.drawOn(c, x, y_top - h); return y_top - h

def _livello_box(c, x, y, res):
    if not res: c.setFont("Helvetica", 9); c.drawString(x, y, "Matrice di rischio: non compilata"); return
    c.setFillColor(LIV_COL.get(res["livello"], ANTRACITE)); c.roundRect(x, y - 4, 150, 18, 4, fill=1, stroke=0); c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10); c.drawString(x + 8, y + 1, f"RISCHIO {res['livello']}  ({res['totale']}/{res['max']})"); c.setFillColor(ANTRACITE)

def _orario(e): return f"{e.get('ora_inizio') or '--:--'} – {e.get('ora_fine') or '--:--'}"

def _coord(lat, lon): return f"{lat:.5f}, {lon:.5f}" if lat is not None else None

def _strip_meteo(c, d, x, y):
    sl = (d["meteo"] or {}).get("slots") or []
    if not sl: return y
    c.setFont("Helvetica-Bold", 9); c.drawString(x, y, "Meteo"); X = x + 110
    for sx in sl:
        if sx.get("code") is not None: renderPDF.draw(icona(categoria(sx["code"])), c, X, y - 6)
        c.setFont("Helvetica", 8); c.drawString(X + 28, y + 1, f"{sx['ora']}  {sx['t']:.0f}°C"); c.drawString(X + 28, y - 8, f"{sx['vento']:.0f} km/h")
        X += 100
    return y - 26

def _riepilogo(c, d, per, n):
    e = d["e"]; so = per.startswith("SALA"); _testata(c, d, f"RIEPILOGO ADDESTRAMENTO – {per}", n)
    rv = (_coord(e["rv_lat"], e["rv_lon"]) or "") + (" – " + e["rv_descr"] if e.get("rv_descr") else "")
    am = (_coord(e.get("amb_lat"), e.get("amb_lon")) or "") + (" – " + e["amb_descr"] if e.get("amb_descr") else "")
    righe = [("Data", e["data"]), ("Orario", _orario(e)), ("Tipologia", d["tipologia"]), ("Squadra", e["team"]), ("Organizzatore", d["org_label"]),
             ("Responsabile", d["resp_nome"]), ("Area (lat, lon)", _coord(e["lat"], e["lon"])), ("RV elicottero", rv), ("RV ambulanza", am), ("Partecipanti", len(d["chk"]))]
    if not so: righe.append(("Canali radio", d["org"].get("radio") or "—"))
    y = _righe(c, M, H - 80, righe, wt=420)
    _livello_box(c, M, y - 8, d["risultato"]); y -= 28
    if not so: y = _strip_meteo(c, d, M, y - 4) - 4
    if so:
        if d["meteo"] and d["meteo"].get("slots"):
            c.setFont("Helvetica-Bold", 9); c.drawString(M, y, "Meteo previsto (passi di 3 h)"); y -= 4
            rows = [["", "Ora", "Condizioni", "T °C", "Pioggia mm", "Vento km/h"]] + [[icona(categoria(s["code"])) if s.get("code") is not None else "", s["ora"], s["descr"], s["t"], s["pioggia"], s["vento"]] for s in d["meteo"]["slots"]]
            y = _tabella(c, rows, [34, 45, 160, 45, 70, 70], M, y) - 10
        c.setFont("Helvetica-Bold", 9); c.drawString(M, y, "Canali radio"); c.setFont("Helvetica", 9)
        for ln in simpleSplit(d["org"].get("radio") or "—", "Helvetica", 9, W - 2 * M): y -= 11; c.drawString(M, y, ln)
        y -= 14
    _legenda(c, M, y - 22)
    mappa(c, M, M + 20, W - 2 * M, max(200, y - 22 - M - 30), d["area"], d["rv"], d.get("amb"), d["tile_fn"])

def _organizzazione(c, d, n):
    o = d["org"]; _testata(c, d, "ORGANIZZAZIONE DELL'ADDESTRAMENTO", n)
    y = _righe(c, M, H - 80, [("Canali radio", o.get("radio")), ("Veterinario", (o.get("veterinario") or "non previsto")), ("Note", o.get("note"))], wt=420) - 6
    c.setFont("Helvetica-Bold", 10); c.drawString(M, y, "Attrezzature e mezzi – responsabili"); y -= 4
    voci = [r for r in (o.get("risorse") or []) if r.get("voce")] or [{"voce": "", "resp": ""}] * 3
    y = _tabella(c, [["Attrezzatura / mezzo", "Responsabile"]] + [[r["voce"], r.get("resp", "")] for r in voci], [300, 220], M, y) - 16
    c.setFont("Helvetica-Bold", 10); c.drawString(M, y, "Partecipanti e ruolo ICS"); y -= 4
    _tabella(c, [["Nominativo", "Codice fiscale", "Comando", "Ruolo ICS"]] + [[p["nome"], p.get("cf") or "—", p["comando"], p["ruolo"]] for p in d["chk"]], [140, 105, 100, 175], M, y)

def _matrice(c, d, n):
    r = d["risultato"]; _testata(c, d, "MATRICE DI RISCHIO", n)
    if not r: c.setFont("Helvetica", 11); c.drawString(M, H - 90, "Matrice non compilata."); return
    c.setFont("Helvetica-Bold", 10); c.drawString(M, H - 76, r["nome"]); _livello_box(c, W - M - 150, H - 80, r)
    dr = Drawing(250, 230); sp = SpiderChart(); sp.x, sp.y, sp.width, sp.height = 45, 25, 160, 180
    sp.data = [[max(0.02, min(1, x["punti"] / x["max"])) for x in r["righe"]]]; sp.labels = [x["codice"] for x in r["righe"]]
    sp.strands[0].fillColor = colors.Color(0.72, 0.11, 0.11, 0.25); sp.strands[0].strokeColor = ROSSO; sp.strands.strokeWidth = 1.2
    sp.spokeLabels.fontSize = 6; sp.spokes.strokeColor = colors.grey; sp.spokes.strokeWidth = 0.3; dr.add(sp)
    renderPDF.draw(dr, c, (W - 250) / 2, H - 330)
    righe = [["Cod.", "Fattore", "Scelta", "Punti", "Max"]] + [[x["codice"], x["fattore"], x["scelta"], str(x["punti"]), str(x["max"])] for x in r["righe"]]
    y = _tabella(c, righe, [32, 190, 230, 30, 30], M, H - 334, size=6.5)
    c.setFont("Helvetica-Bold", 9); c.drawString(M, y - 14, f"Totale {r['totale']} / {r['max']}  ({r['pct']}%) – soglie: medio da {r['soglia_medio']}%, alto da {r['soglia_alto']}%")

def _ics(c, d, n):
    _testata(c, d, "SCHEMA ICS", n); per_ruolo = {}
    for p in d["chk"]: per_ruolo.setdefault(p["ruolo_cod"], []).append(p["nome"])
    righe = {}
    for r in d["ics"]: righe.setdefault(r["riga"], []).append(r)
    y = H - 100; centri = {}
    for riga in sorted(righe):
        ruoli = righe[riga]; bw = min(150, (W - 2 * M) / len(ruoli) - 8); bh = 62 if riga != 5 else 90
        for i, r in enumerate(ruoli):
            x = W / 2 + (i - (len(ruoli) - 1) / 2) * (bw + 8) - bw / 2
            c.setFillColor(colors.HexColor("#FAFAFA")); c.setStrokeColor(ROSSO if riga == 1 else ANTRACITE); c.setLineWidth(1.6 if riga == 1 else .8)
            c.rect(x, y - bh, bw, bh, fill=1); c.setFillColor(ROSSO); c.rect(x, y - 14, bw, 14, fill=1, stroke=0); c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(x + bw / 2, y - 10, simpleSplit(r["nome"], "Helvetica-Bold", 6.5, bw - 6)[0]); c.setFillColor(ANTRACITE); c.setFont("Helvetica", 7)
            yy = y - 25
            for nome in per_ruolo.get(r["codice"], [])[:5]: c.drawCentredString(x + bw / 2, yy, simpleSplit(nome, "Helvetica", 7, bw - 6)[0]); yy -= 9
            if len(per_ruolo.get(r["codice"], [])) > 5: c.drawCentredString(x + bw / 2, yy, f"… +{len(per_ruolo[r['codice']]) - 5}")
            centri[(riga, i)] = (x + bw / 2, y, y - bh)
        if riga > 1:
            c.setStrokeColor(ANTRACITE); c.setLineWidth(.6); c.line(W / 2, y + 14, W / 2, y)
        y -= bh + 26

def _firme(c, d, n0, per_pagina=20):
    ppl = d["chk"]; pagine = max(1, math.ceil(len(ppl) / per_pagina)); n = n0
    for p in range(pagine):
        _testata(c, d, f"FOGLIO FIRME ({p + 1}/{pagine})", n)
        c.setFont("Helvetica", 9); c.drawString(M, H - 76, f"{d['tipologia']} – squadra {d['e']['team']} – {d['e']['data']} – {_orario(d['e'])} – {d['org_label']}")
        blocco = ppl[p * per_pagina:(p + 1) * per_pagina]; blocco = blocco + [{"nome": "", "cf": "", "comando": "", "ruolo": ""}] * (per_pagina - len(blocco))
        _tabella(c, [["N.", "Cognome e nome", "Codice fiscale", "Comando", "Ruolo ICS", "Firma entrata", "Firma uscita"]] + [[str(p * per_pagina + i + 1), x["nome"], x.get("cf", ""), x["comando"], x["ruolo"], "", ""] for i, x in enumerate(blocco)],
                 [20, 105, 92, 58, 78, 85, 85], M, H - 90, size=7, extra=[("MINROWHEIGHT", (0, 1), (-1, -1), 28)] if False else [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")])])
        c.showPage(); n += 1
    return n

def piano_pdf(d, tipo="completo"):
    """tipo: 'completo' (7+ pagine) | 'ridotto' (pagine 3, 4 e fogli firme). Ritorna bytes."""
    b = io.BytesIO(); c = canvas.Canvas(b, pagesize=A4); c.setTitle("Piano di sicurezza " + d["cod_add"]); c.setAuthor("P.U.M.A."); n = 1
    if tipo == "completo":
        _riepilogo(c, d, "FUNZIONARIO DI GUARDIA", n); c.showPage(); n += 1
        c.showPage(); n += 1                       # pagina 2 vuota (fronte/retro)
    _riepilogo(c, d, "SALA OPERATIVA", n); c.showPage(); n += 1
    _organizzazione(c, d, n); c.showPage(); n += 1
    if tipo == "completo":
        _matrice(c, d, n); c.showPage(); n += 1
        _ics(c, d, n); c.showPage(); n += 1
    _firme(c, d, n); c.save(); return b.getvalue()

def manovre_pdf(d, titolo, gruppi):
    """Allegato: solo le manovre della specializzazione. gruppi = [(intestazione, [(etichetta)...])]."""
    b = io.BytesIO(); c = canvas.Canvas(b, pagesize=A4); c.setTitle("Manovre " + d["cod_add"]); n = 1; _testata(c, d, titolo, n); y = H - 84
    for head, voci in gruppi:
        if y < 90: c.showPage(); n += 1; _testata(c, d, titolo, n); y = H - 84
        c.setFont("Helvetica-Bold", 10); c.setFillColor(ROSSO); c.drawString(M, y, head); c.setFillColor(ANTRACITE); y -= 14
        for v in voci:
            lines = simpleSplit(v, "Helvetica", 9, W - 2 * M - 24)
            if y < 50 + 11 * len(lines): c.showPage(); n += 1; _testata(c, d, titolo, n); y = H - 84
            c.rect(M, y - 1, 8, 8); c.setFont("Helvetica", 9)
            for ln in lines: c.drawString(M + 16, y, ln); y -= 11
            y -= 3
        y -= 8
    c.save(); return b.getvalue()
