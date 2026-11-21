"""Piano di sicurezza P.U.M.A.: meteo a passi di 3 h, organizzazione, matrici di rischio, PDF, invio alle SO."""
import json, os, re, sqlite3, urllib.parse, urllib.request
from datetime import date, datetime
from flask import render_template, request, redirect, url_for, flash, abort, Response, current_app
from . import bp as puma_bp, current_user, can_write, get_db
from .addestramenti import db, ev_get, manda, WMO, tile_bytes, _resp
from . import piano_pdf

DATI = os.path.join(os.path.dirname(__file__), "dati")
ROM = {"I": 1, "II": 2, "III": 3, "IV": 4}
CORSO_LIVELLO = {"BAS": "SAF (Speleo Alpino Fluviale) BASICO", "AVA": "SAF (Speleo Alpino Fluviale) AVANZATO", "TPS": "TPSS (Tecniche di Primo Soccorso Sanitario)"}
_seeded = False

# ---------- import iniziale (solo se le tabelle sono vuote: le modifiche successive restano) ----------
def seed():
    d = db()
    try:
        if not d.execute("SELECT 1 FROM puma_matrici LIMIT 1").fetchone():
            m = f = None; o = 0
            for riga in open(os.path.join(DATI, "matrici.txt"), encoding="utf-8"):
                p = riga.rstrip("\n").split("|")
                if p[0] == "M": m = p[1]; d.execute("INSERT INTO puma_matrici(codice,nome) VALUES(?,?)", (p[1], p[2])); n = 0
                elif p[0] == "F": n += 1; f = d.execute("INSERT INTO puma_fattori(matrice,codice,descrizione,peso_max,ordine) VALUES(?,?,?,?,?)", (m, p[1], p[2], int(p[3]), n)).lastrowid; o = 0
                elif p[0] == "O": o += 1; d.execute("INSERT INTO puma_opzioni(fattore_id,testo,punteggio,ordine) VALUES(?,?,?,?)", (f, p[1], int(p[2]), o))
        # manovre di serie (dati/manovre.txt): aggiunge quelle che mancano, tranne nei corsi importati dal foglio PUMA
        liv = {r["nome"]: r["id"] for r in d.execute("SELECT id,nome FROM puma_livelli")}
        dal_foglio = {r[0] for r in d.execute("SELECT DISTINCT livello_id FROM puma_manovre WHERE da_foglio=1")}
        for riga in open(os.path.join(DATI, "manovre.txt"), encoding="utf-8"):
            if riga.startswith("#") or not riga.strip(): continue
            corso, ciclo, nr, nome = riga.rstrip("\n").split("|"); nr = int(nr); lid = liv.get(CORSO_LIVELLO[corso])
            if not lid or lid in dal_foglio: continue
            cod = f"{corso}_{ciclo}_{nr:03d}"
            if d.execute("SELECT 1 FROM puma_manovre WHERE livello_id=? AND codice=?", (lid, cod)).fetchone(): continue
            et = f"{ciclo} {'Parte' if corso == 'TPS' else 'Ciclo'} - {nr} - {nome}"
            m = re.search(r"\(([A-Z])\)\s*$", nome)
            d.execute("INSERT INTO puma_manovre(livello_id,nome,ordine,corso,codice,ciclo,numero,lettera,testo) VALUES(?,?,?,?,?,?,?,?,?)",
                      (lid, et, ROM.get(ciclo, 9) * 100 + nr, corso, cod, ciclo, nr, m.group(1) if m else None, et))
        # lettera (A/B/C/N) anche sulle manovre di serie caricate prima
        for r in d.execute("SELECT id, nome FROM puma_manovre WHERE lettera IS NULL OR lettera=''").fetchall():
            m = re.search(r"\(([A-Z])\)\s*$", r["nome"] or "")
            if m: d.execute("UPDATE puma_manovre SET lettera=? WHERE id=?", (m.group(1), r["id"]))
        d.commit()
    except sqlite3.IntegrityError:
        d.rollback()   # un altro processo ha già importato

@puma_bp.before_request
def _seed_una_volta():
    global _seeded
    if not _seeded:
        try: seed(); _seeded = True
        except Exception: current_app.logger.exception("P.U.M.A.: importazione dati iniziali non riuscita")

# ---------- matrici di rischio ----------
def matrice(cod):
    m = db().execute("SELECT * FROM puma_matrici WHERE codice=?", (cod,)).fetchone()
    if not m: return None
    fs = []
    for f in db().execute("SELECT * FROM puma_fattori WHERE matrice=? ORDER BY ordine", (cod,)):
        fs.append({**dict(f), "opzioni": [dict(o) for o in db().execute("SELECT * FROM puma_opzioni WHERE fattore_id=? ORDER BY ordine", (f["id"],))]})
    return {**dict(m), "fattori": fs}

def calcola(cod, risposte):
    """risposte: {fattore_id: opzione_id}. Livello da % sul massimo; un'opzione da 100 punti = CRITICO (addestramento non ammissibile così com'è)."""
    mx = matrice(cod)
    if not mx: return None
    righe, tot, critico, ok = [], 0, False, True
    for f in mx["fattori"]:
        o = next((o for o in f["opzioni"] if str(o["id"]) == str(risposte.get(str(f["id"])))), None)
        if not o: ok = False; continue
        tot += o["punteggio"]; critico |= o["punteggio"] >= 100
        righe.append({"codice": f["codice"], "fattore": f["descrizione"], "scelta": o["testo"], "punti": o["punteggio"], "max": f["peso_max"]})
    mxt = sum(f["peso_max"] for f in mx["fattori"]); pct = round(tot / mxt * 100) if mxt else 0
    liv = "CRITICO" if critico else "ALTO" if pct >= mx["soglia_alto"] else "MEDIO" if pct >= mx["soglia_medio"] else "BASSO"
    return {"matrice": cod, "nome": mx["nome"], "righe": righe, "totale": tot, "max": mxt, "pct": pct, "livello": liv, "completo": ok,
            "soglia_medio": mx["soglia_medio"], "soglia_alto": mx["soglia_alto"]}

# ---------- meteo a passi di 3 ore nella fascia dell'addestramento ----------
def meteo_slots(lat, lon, giorno, ora_i, ora_f):
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "timezone": "auto", "start_date": giorno, "end_date": giorno,
                                "hourly": "temperature_2m,precipitation,wind_speed_10m,weather_code"})
    with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=8) as r: h = json.load(r)["hourly"]
    hi, hf = int((ora_i or "08:00")[:2]), int((ora_f or "17:00")[:2]); slots = []
    for H_ in range(hi, hf + 1, 3):
        k = H_ if H_ < len(h["time"]) else len(h["time"]) - 1
        slots.append({"ora": f"{H_:02d}:00", "t": h["temperature_2m"][k], "pioggia": h["precipitation"][k], "vento": h["wind_speed_10m"][k],
                      "code": h["weather_code"][k], "descr": WMO.get(h["weather_code"][k], f"codice {h['weather_code'][k]}")})
    return {"slots": slots, "rilevato": datetime.now().strftime("%d/%m/%Y %H:%M")}

EMOJI = {"sole": "☀️", "poco": "🌤️", "parz": "⛅", "coperto": "☁️", "nebbia": "🌫️", "pioggia": "🌧️", "neve": "🌨️", "temporale": "⛈️"}

@puma_bp.app_template_filter("meteo_icona")
def _meteo_icona(code):
    return EMOJI.get(piano_pdf.categoria(code), "") if code is not None else ""

# ---------- pagina del piano ----------
def _org(e): return json.loads(e["organizzazione"] or "{}")

@puma_bp.route("/collettivi/<int:i>/piano")
def piano(i):
    u, e = _resp(i)
    cod = request.args.get("m") or e["matrice"] or "A"
    saved = json.loads(e["rischio"] or "{}") if (e["matrice"] == cod) else {}
    mx = matrice(cod); ris = calcola(cod, saved.get("risposte", {})) if mx else None
    return render_template("puma/piano.html", e=e, org=_org(e), meteo=json.loads(e["meteo"] or "null"), mx=mx, ris=ris, risposte=saved.get("risposte", {}),
                           matrici=db().execute("SELECT codice,nome FROM puma_matrici ORDER BY codice").fetchall(), cod=cod,
                           n_manovre=len(manovre_evento(e)), pdf_ok=True)

@puma_bp.post("/collettivi/<int:i>/piano/meteo")
def piano_meteo(i):
    u, e = _resp(i)
    if e["lat"] is None: flash("Imposta prima le coordinate dell'area."); return redirect(url_for("puma.piano", i=i))
    try:
        db().execute("UPDATE puma_eventi SET meteo=? WHERE id=?", (json.dumps(meteo_slots(e["lat"], e["lon"], e["data"], e["ora_inizio"], e["ora_fine"])), i)); db().commit()
    except Exception as x:
        flash("Meteo non disponibile (%s). Le previsioni arrivano fino a circa 16 giorni e il server deve raggiungere internet." % type(x).__name__)
    return redirect(url_for("puma.piano", i=i))

@puma_bp.post("/collettivi/<int:i>/piano/organizzazione")
def piano_organizzazione(i):
    u, e = _resp(i); f = request.form; risorse = []
    for riga in f.get("risorse", "").splitlines():
        if riga.strip(): v, _, r = riga.partition("|"); risorse.append({"voce": v.strip(), "resp": r.strip()})
    org = {"radio": f.get("radio", "").strip(), "veterinario": f.get("veterinario", "").strip(), "note": f.get("note", "").strip(), "risorse": risorse}
    db().execute("UPDATE puma_eventi SET organizzazione=? WHERE id=?", (json.dumps(org), i)); db().commit()
    flash("Organizzazione salvata."); return redirect(url_for("puma.piano", i=i))

@puma_bp.post("/collettivi/<int:i>/piano/matrice")
def piano_matrice(i):
    u, e = _resp(i); cod = request.form["m"]
    ris = {k[2:]: v for k, v in request.form.items() if k.startswith("r_")}
    r = calcola(cod, ris)
    if not r: abort(404)
    db().execute("UPDATE puma_eventi SET matrice=?, rischio=? WHERE id=?", (cod, json.dumps({"risposte": ris, "livello": r["livello"], "totale": r["totale"], "max": r["max"]}), i)); db().commit()
    flash("Matrice salvata: rischio %s (%s/%s)%s" % (r["livello"], r["totale"], r["max"], "" if r["completo"] else " – attenzione: ci sono fattori non compilati"))
    return redirect(url_for("puma.piano", i=i))

# ---------- PDF ----------
def manovre_evento(e):
    q = "SELECT m.*, l.nome livello FROM puma_manovre m JOIN puma_livelli l ON l.id=m.livello_id WHERE "
    if e["livello_id"]: rows = db().execute(q + "m.livello_id=? ORDER BY m.ordine, m.id", (e["livello_id"],))
    else: rows = db().execute(q + "l.settore=? ORDER BY l.nome, m.ordine, m.id", (e["tipologia"],))
    return rows.fetchall()

def dati_pdf(e):
    d = db(); k = d.execute("SELECT k.nome, k.sigla, dz.nome dir FROM comandi k LEFT JOIN puma_comando_dir cd ON cd.comando_id=k.id LEFT JOIN puma_direzioni dz ON dz.id=cd.direzione_id WHERE k.id=?", (e["comando_id"],)).fetchone()
    resp = d.execute("SELECT nome, cognome FROM utenti WHERE email=?", (e["responsabile"],)).fetchone()
    nomi = {r["id"]: r["nome"] for r in d.execute("SELECT id,nome FROM comandi")}
    ruoli = {r["codice"]: r for r in d.execute("SELECT * FROM puma_ics_ruoli")}
    cfs = {r["email"]: r["codice_fiscale"] for r in d.execute("SELECT u.email, p.codice_fiscale FROM puma_persone p JOIN utenti u ON u.id=p.utente_id")}
    chk = [{"nome": c["nome"], "cf": cfs.get(c["username"], ""), "comando": nomi.get(c["comando_origine"], ""), "ruolo_cod": c["ruolo_ics"] or "OPER", "ruolo": ruoli[c["ruolo_ics"] or "OPER"]["nome"]}
           for c in d.execute("SELECT * FROM puma_checkin WHERE evento_id=? ORDER BY ora", (e["id"],))]
    liv = d.execute("SELECT nome FROM puma_livelli WHERE id=?", (e["livello_id"],)).fetchone() if e["livello_id"] else None
    saved = json.loads(e["rischio"] or "{}"); ris = calcola(e["matrice"], saved.get("risposte", {})) if e["matrice"] else None
    return {"e": dict(e), "cod_add": e["cod_add"] or f"{e['tipologia']}-{e['team'].upper()}-{e['data']}",
            "org_label": f"Direzione Regionale {k['dir'] or ''}".strip() if e["org_dr"] else f"Comando VVF {k['nome']}",
            "resp_nome": f"{resp['nome']} {resp['cognome']}".strip() if resp else e["responsabile"], "tipologia": e["tipologia"] + (f" – {liv['nome']}" if liv else ""),
            "chk": chk, "org": _org(e), "meteo": json.loads(e["meteo"] or "null"), "risultato": ris, "ics": [dict(r) for r in ruoli.values()],
            "area": (e["lat"], e["lon"]) if e["lat"] is not None else None, "rv": (e["rv_lat"], e["rv_lon"]) if e["rv_lat"] is not None else None,
            "amb": (e["amb_lat"], e["amb_lon"]) if e["amb_lat"] is not None else None,
            "tile_fn": tile_bytes, "generato": datetime.now().strftime("%d/%m/%Y %H:%M")}

def pdf_manovre(e):
    gruppi = {}
    for m in manovre_evento(e):
        chiave = f"{m['livello']} – " + (f"{m['ciclo']} {'Parte' if m['corso'] == 'TPS' else 'Ciclo'}" if m["ciclo"] else "altre manovre")
        gruppi.setdefault(chiave, []).append(m["nome"])
    return piano_pdf.manovre_pdf(dati_pdf(e), "MANOVRE DELLA SPECIALIZZAZIONE", list(gruppi.items())) if gruppi else None

@puma_bp.route("/collettivi/<int:i>/piano/pdf/<tipo>")
def piano_scarica(i, tipo):
    u = current_user(); e = ev_get(i, u)
    if tipo == "manovre": data = pdf_manovre(e) or abort(404)
    elif tipo in ("completo", "ridotto"): data = piano_pdf.piano_pdf(dati_pdf(e), tipo)
    else: abort(404)
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": f'inline; filename="{(e["cod_add"] or "piano")}_{tipo}.pdf"'})

def destinatari(cid):
    """Indirizzi per l'invio del piano: quelli delle Impostazioni (SO, ROP, ROR, SODIR, Formazione, TEP) più le mail
    TEP e Formazione della scheda del Comando (Comandi e Direzioni), se non già presenti."""
    out = [r["email"] for r in db().execute("SELECT DISTINCT email FROM puma_destinatari WHERE comando_id=?", (cid,))]
    k = db().execute("SELECT email_tep, email_formazione FROM comandi WHERE id=?", (cid,)).fetchone()
    for x in (k or []):
        if x and x.lower() not in [o.lower() for o in out]: out.append(x)
    return out

@puma_bp.post("/collettivi/<int:i>/piano/invia")
def piano_invia(i):
    u, e = _resp(i); tipo = "ridotto" if request.form.get("ridotto") else "completo"
    if tipo == "completo" and not e["rischio"]: flash("Per il piano completo compila prima la matrice di rischio (oppure invia la versione ridotta)."); return redirect(url_for("puma.piano", i=i))
    dest = destinatari(e["comando_id"])
    if not dest: flash("Nessun destinatario configurato (Impostazioni)."); return redirect(url_for("puma.piano", i=i))
    cod = e["cod_add"] or "piano"; allegati = [(f"{cod}_{tipo}.pdf", piano_pdf.piano_pdf(dati_pdf(e), tipo))]
    man = pdf_manovre(e)
    if man: allegati.append((f"{cod}_manovre.pdf", man))
    try:
        manda(dest, f"[P.U.M.A.] Piano di sicurezza {cod}", f"In allegato il piano di sicurezza dell'addestramento {cod} ({e['data']}, {e['ora_inizio']}-{e['ora_fine']}).", allegati)
        db().execute("UPDATE puma_eventi SET piano_inviato=? WHERE id=?", (datetime.now().isoformat(timespec="minutes"), i)); db().commit()
        flash("Piano (%s) inviato a %d destinatari." % (tipo, len(dest)))
    except Exception as x: flash("Invio non riuscito: %s" % x)
    return redirect(url_for("puma.piano", i=i))
