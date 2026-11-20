"""Moduli P.U.M.A.: collettivi (workflow responsabile), individuali, interventi reali, mappa live, scadenze."""
import json, smtplib, ssl, urllib.request, urllib.parse
from calendar import monthrange
from datetime import date, datetime
from email.message import EmailMessage
from flask import g, render_template, request, redirect, url_for, flash, abort, jsonify, current_app
import os, re, time
from flask import send_file, Response
import config
from . import bp as puma_bp, current_user, can_write, get_db, scope_sql, elenco, tenant_vals, settore_ok, email_utente, conf, _puo

TEAM = ["Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliett", "Kilo", "Lima", "Mike",
        "November", "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "X-ray", "Yankee", "Zulu"]
RUOLI_MAIL = ["SO", "ROP", "ROR", "SODIR", "FORMAZIONE", "TEP"]
FATTORI = ["Condizioni meteo", "Terreno / ambiente", "Complessità delle manovre", "Esperienza dei partecipanti"]
WMO = {0: "sereno", 1: "prevalentemente sereno", 2: "parzialmente nuvoloso", 3: "coperto", 45: "nebbia", 48: "nebbia con brina",
       51: "pioggerella", 61: "pioggia debole", 63: "pioggia", 65: "pioggia forte", 71: "neve debole", 73: "neve", 75: "neve forte",
       80: "rovesci", 95: "temporale", 96: "temporale con grandine"}

def db(): return get_db()
def cfg(cid, k, d=None):
    r = db().execute("SELECT valore FROM puma_config WHERE comando_id=? AND chiave=?", (cid, k)).fetchone()
    return r["valore"] if r else d
def add_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12); y += d.year
    return date(y, mo + 1, min(d.day, monthrange(y, mo + 1)[1]))
def ev_get(i, u):
    r = db().execute("SELECT * FROM puma_eventi WHERE id=? AND (is_blindato=0 OR comando_id=?)", (i, u["comando_id"])).fetchone()
    return r or abort(404)
def cod_add(d, tipologia, team, comando_id, org_dr, data):
    """COD_ADD = TIPOLOGIA-SQUADRA-<SIGLA DIREZIONE><SIGLA COMANDO | DR>-AAAAMMGG  (es. SAF-ALFA-VENBL-20261006; se organizza la Direzione: SAF-ALFA-VENDR-...)."""
    r = d.execute("""SELECT k.sigla cmd, COALESCE(dz.sigla,'XXX') dir FROM comandi k LEFT JOIN puma_comando_dir cd ON cd.comando_id=k.id
        LEFT JOIN puma_direzioni dz ON dz.id=cd.direzione_id WHERE k.id=?""", (comando_id,)).fetchone()
    return f"{tipologia.upper()}-{team.upper()}-{r['dir']}{'DR' if org_dr else r['cmd']}-{data.replace('-', '')}"

_CF_ODD = dict(zip("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", [1,0,5,7,9,13,15,17,19,21,1,0,5,7,9,13,15,17,19,21,2,4,18,20,11,3,6,8,12,14,16,10,22,25,24,23]))
def cf_valido(cf):
    """Controllo formale del codice fiscale (16 caratteri, omocodia ammessa, carattere di controllo)."""
    cf = (cf or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPR-T][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]", cf): return False
    tot = sum(_CF_ODD[ch] if i % 2 == 0 else (int(ch) if ch.isdigit() else ord(ch) - 65) for i, ch in enumerate(cf[:15]))
    return cf[15] == chr(65 + tot % 26)

def livelli(): return db().execute("SELECT * FROM puma_livelli ORDER BY settore,nome").fetchall()
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

# ---------------- 1. COLLETTIVI ----------------
@puma_bp.route("/collettivi")
def collettivi():
    u = current_user()
    aperti = [e for e in db().execute("""SELECT * FROM puma_eventi WHERE data=? AND stato!='chiuso' AND is_blindato=0 AND comando_id!=?
        ORDER BY comando_id, team""", (date.today().isoformat(), u["comando_id"])) if settore_ok(u, e["tipologia"])]
    q = request.args.get("quando", "oggi"); oggi = date.today().isoformat(); giorno = request.args.get("data") or ""
    filtro, par = {"oggi": ("data=?", (oggi,)), "futuri": ("data>?", (oggi,)), "passati": ("data<?", (oggi,)), "giorno": ("data=?", (giorno or oggi,))}.get(q, ("1=1", ()))
    return render_template("puma/collettivi.html", righe=elenco("puma_eventi", u, filtro, par, order="data, ora_inizio, team"), scrivi=can_write(u),
                           aperti=aperti, livello=u["livello"], quando=q, giorno=giorno)

@puma_bp.route("/collettivi/nuovo", methods=["GET", "POST"])
def collettivo_nuovo():
    u = current_user()
    if not can_write(u): abort(403)
    if request.method == "POST":
        f = request.form
        if not settore_ok(u, f["tipologia"], "scrittura"): abort(403)
        try:
            if (f.get("ora_fine") or "23:59") <= (f.get("ora_inizio") or "00:00"):
                flash("L'ora di fine deve essere successiva all'ora di inizio."); return redirect(request.url)
            org_dr = int(bool(f.get("org_dr")))
            cod = cod_add(db(), f["tipologia"], f["team"], u["comando_id"], org_dr, f["data"])
            c = db().execute("""INSERT INTO puma_eventi(data,ora_inizio,ora_fine,org_dr,cod_add,tipologia,livello_id,team,titolo,lat,lon,rv_lat,rv_lon,rv_descr,
              amb_lat,amb_lon,amb_descr,responsabile,comando_id,direzione_id,is_blindato,is_condiviso_nazionale) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (f["data"], f.get("ora_inizio") or "08:00", f.get("ora_fine") or "17:00", org_dr, cod, f["tipologia"], f.get("livello_id") or None, f["team"], f.get("titolo"),
               num(f.get("lat")), num(f.get("lon")), num(f.get("rv_lat")), num(f.get("rv_lon")), f.get("rv_descr"),
               num(f.get("amb_lat")), num(f.get("amb_lon")), f.get("amb_descr"), u["username"], *tenant_vals(u)))
        except Exception:
            flash("Esiste già un addestramento %s – team %s in quella data per il tuo Comando." % (f["tipologia"], f["team"]))
            return redirect(request.url)
        db().commit(); return redirect(url_for("puma.collettivo", i=c.lastrowid))
    return render_template("puma/collettivo_nuovo.html", team=TEAM, livelli=livelli(), oggi=date.today().isoformat())

@puma_bp.route("/collettivi/<int:i>")
def collettivo(i):
    u = current_user(); e = ev_get(i, u)
    chk = db().execute("SELECT * FROM puma_checkin WHERE evento_id=? ORDER BY ora", (i,)).fetchall()
    mio = any(c["username"] == u["username"] for c in chk)
    return render_template("puma/collettivo.html", e=e, chk=chk, mio=mio, resp=(e["comando_id"] == u["comando_id"] and can_write(u)),
                           abilitato=settore_ok(u, e["tipologia"]), ruoli=ics_ruoli(), oggi=date.today().isoformat())

def ics_ruoli(): return db().execute("SELECT * FROM puma_ics_ruoli ORDER BY ordine").fetchall()

@puma_bp.route("/collettivi/<int:i>/partecipa", methods=["GET", "POST"])
def partecipa(i):
    """Passo 1 (GET): riepilogo + scelta del ruolo ICS. Passo 2 (POST con conferma): 'è l'addestramento giusto?' -> registrazione."""
    u = current_user(); e = ev_get(i, u)
    if not settore_ok(u, e["tipologia"]): abort(403)
    if e["data"] != date.today().isoformat() or e["stato"] == "chiuso":
        flash("La registrazione è possibile solo il giorno dell'addestramento."); return redirect(url_for("puma.collettivo", i=i))
    ruoli = ics_ruoli()
    if request.method == "POST":
        r = request.form.get("ruolo")
        if r not in [x["codice"] for x in ruoli]: flash("Scegli il tuo ruolo ICS."); return redirect(request.url)
        if not request.form.get("conferma"): flash("Conferma che è l'addestramento giusto."); return redirect(request.url)
        cf = request.form.get("cf", "").strip().upper()
        if not cf_valido(cf): flash("Codice fiscale non valido: controlla i 16 caratteri."); return redirect(request.url)
        uid = g.utente["id"]
        db().execute("INSERT INTO puma_persone(utente_id,codice_fiscale) VALUES(?,?) ON CONFLICT(utente_id) DO UPDATE SET codice_fiscale=excluded.codice_fiscale", (uid, cf))
        db().execute("""INSERT INTO puma_checkin(evento_id,username,nome,comando_origine,ora,ruolo_ics) VALUES(?,?,?,?,?,?)
            ON CONFLICT(evento_id,username) DO UPDATE SET ruolo_ics=excluded.ruolo_ics""", (i, u["username"], u.get("nome", u["username"]), u["comando_id"], datetime.now().strftime("%H:%M"), r))
        db().execute("UPDATE puma_eventi SET stato='attivo' WHERE id=? AND stato='programmato'", (i,)); db().commit()
        flash("Registrazione effettuata."); return redirect(url_for("puma.collettivo", i=i))
    mio = db().execute("SELECT ruolo_ics FROM puma_checkin WHERE evento_id=? AND username=?", (i, u["username"])).fetchone()
    p = db().execute("SELECT codice_fiscale FROM puma_persone WHERE utente_id=?", (g.utente["id"],)).fetchone()
    return render_template("puma/partecipa.html", e=e, ruoli=ruoli, mio=mio["ruolo_ics"] if mio else None, cf=p["codice_fiscale"] if p else "")

def _resp(i):
    u = current_user(); e = ev_get(i, u)
    if not (e["comando_id"] == u["comando_id"] and can_write(u)): abort(403)
    return u, e

@puma_bp.post("/collettivi/<int:i>/convalida")
def convalida(i):
    u, e = _resp(i); ids = request.form.getlist("ok")
    for r in db().execute("SELECT username FROM puma_checkin WHERE evento_id=?", (i,)).fetchall():
        v = request.form.get("ruolo_" + r["username"])
        if v: db().execute("UPDATE puma_checkin SET ruolo_ics=? WHERE evento_id=? AND username=?", (v, i, r["username"]))
    db().execute("UPDATE puma_checkin SET convalidato=0 WHERE evento_id=?", (i,))
    for x in ids: db().execute("UPDATE puma_checkin SET convalidato=1 WHERE evento_id=? AND username=?", (i, x))
    if request.form.get("chiudi"): db().execute("UPDATE puma_eventi SET stato='chiuso' WHERE id=?", (i,))
    db().commit(); flash("Presenze convalidate."); return redirect(url_for("puma.collettivo", i=i))

def manda(dest, oggetto, corpo, allegati=()):
    if not conf("PUMA_SMTP_HOST"): raise RuntimeError("PUMA_SMTP_HOST non configurato")
    m = EmailMessage(); m["Subject"], m["From"], m["To"] = oggetto, conf("PUMA_MAIL_FROM", "puma@vigilfuoco.it"), ", ".join(dest)
    m.set_content(corpo)
    for nome, dati in allegati: m.add_attachment(dati, maintype="application", subtype="pdf", filename=nome)
    with smtplib.SMTP(conf("PUMA_SMTP_HOST"), int(conf("PUMA_SMTP_PORT", 25)), timeout=15) as s:
        if conf("PUMA_SMTP_TLS"): s.starttls(context=ssl.create_default_context())
        if conf("PUMA_SMTP_USER"): s.login(conf("PUMA_SMTP_USER"), conf("PUMA_SMTP_PASS", ""))
        s.send_message(m)

# ---------------- 2. INDIVIDUALI / 3. INTERVENTI ----------------
@puma_bp.route("/individuali", methods=["GET", "POST"])
def individuali():
    u = current_user()
    if request.method == "POST":
        f = request.form
        if not settore_ok(u, f["tipologia"]): abort(403)
        db().execute("""INSERT INTO puma_individuali(username,tipologia,livello_id,inizio,fine,manovre,comando_id,direzione_id,is_blindato,
            is_condiviso_nazionale) VALUES(?,?,?,?,?,?,?,?,0,0)""", (u["username"], f["tipologia"], f.get("livello_id") or None,
            f["inizio"], f["fine"], json.dumps(f.getlist("manovre")), u["comando_id"], u.get("direzione_id")))
        db().commit(); flash("Addestramento individuale registrato."); return redirect(url_for("puma.individuali"))
    mie = db().execute("""SELECT i.*, l.nome livello FROM puma_individuali i LEFT JOIN puma_livelli l ON l.id=i.livello_id
        WHERE username=? ORDER BY inizio DESC""", (u["username"],)).fetchall()
    return render_template("puma/individuali.html", righe=mie, livelli=[l for l in livelli() if settore_ok(u, l["settore"])],
                           adesso=datetime.now().strftime("%Y-%m-%dT%H:%M"))

@puma_bp.route("/api/manovre/<int:lid>")
def api_manovre(lid):
    current_user()
    return jsonify([dict(r) for r in db().execute("SELECT id,nome FROM puma_manovre WHERE livello_id=? ORDER BY ordine,id", (lid,))])

@puma_bp.route("/interventi", methods=["GET", "POST"])
def interventi():
    u = current_user()
    if request.method == "POST":
        f = request.form
        if not settore_ok(u, f["macro"]): abort(403)
        db().execute("""INSERT INTO puma_interventi(username,macro,data,descrizione,comando_id,direzione_id,is_blindato,is_condiviso_nazionale)
            VALUES(?,?,?,?,?,?,0,0)""", (u["username"], f["macro"], f["data"], f.get("descrizione"), u["comando_id"], u.get("direzione_id")))
        db().commit(); flash("Intervento registrato."); return redirect(url_for("puma.interventi"))
    r = db().execute("SELECT * FROM puma_interventi WHERE username=? ORDER BY data DESC", (u["username"],)).fetchall()
    return render_template("puma/interventi.html", righe=r, oggi=date.today().isoformat(),
                           mie=[s for s in db().execute("SELECT * FROM puma_settori") if settore_ok(u, s["codice"])])

# ---------------- 4. MAPPA + DASHBOARD ----------------
@puma_bp.route("/mappa")
def mappa():
    current_user(); return render_template("puma/mappa.html")

@puma_bp.route("/api/attivi")
def api_attivi():
    u = current_user()
    ev = elenco("puma_eventi", u, "data=? AND stato!='chiuso'", (date.today().isoformat(),))
    out = []
    for e in ev:
        n = db().execute("SELECT COUNT(*) c, SUM(convalidato) v FROM puma_checkin WHERE evento_id=?", (e["id"],)).fetchone()
        out.append({"id": e["id"], "tipologia": e["tipologia"], "team": e["team"], "stato": e["stato"], "titolo": e["titolo"],
                    "comando": db().execute("SELECT nome FROM comandi WHERE id=?", (e["comando_id"],)).fetchone()[0], "lat": e["lat"], "lon": e["lon"], "rv": [e["rv_lat"], e["rv_lon"]], "amb": [e["amb_lat"], e["amb_lon"]],
                    "presenti": n["c"], "convalidati": n["v"] or 0, "url": url_for("puma.collettivo", i=e["id"])})
    return jsonify(out)

# ---------------- PROFILO / SCADENZE / SETTORI ----------------
def scadenze(u=None, settore=None, comando=None):
    q = """SELECT x.username, x.comando_id, x.livello_id, MAX(x.d) ultima, l.nome livello, l.settore, l.mesi_validita FROM (
        SELECT c.username, c.comando_origine comando_id, e.livello_id, e.data d FROM puma_checkin c JOIN puma_eventi e ON e.id=c.evento_id
          WHERE c.convalidato=1 AND e.livello_id IS NOT NULL
        UNION ALL SELECT username, comando_id, livello_id, substr(inizio,1,10) FROM puma_individuali WHERE livello_id IS NOT NULL) x
        JOIN puma_livelli l ON l.id=x.livello_id WHERE 1=1"""
    p = []
    if u: q += " AND x.username=?"; p.append(u)
    if settore: q += " AND l.settore=?"; p.append(settore)
    if comando is not None:
        comando = [comando] if isinstance(comando, int) else list(comando)
        q += " AND x.comando_id IN (%s)" % ",".join("?" * len(comando)) if comando else " AND 0"; p += comando
    out = []
    for r in db().execute(q + " GROUP BY x.username, x.livello_id ORDER BY l.settore, x.username", p):
        sc = add_months(date.fromisoformat(r["ultima"]), r["mesi_validita"])
        out.append({**dict(r), "scadenza": sc.isoformat(), "giorni": (sc - date.today()).days})
    return out

@puma_bp.route("/profilo")
def profilo():
    u = current_user()
    ind = db().execute("SELECT i.*, l.nome livello FROM puma_individuali i LEFT JOIN puma_livelli l ON l.id=i.livello_id WHERE username=? ORDER BY inizio DESC", (u["username"],)).fetchall()
    col = db().execute("""SELECT e.data,e.tipologia,e.team,l.nome livello,c.convalidato FROM puma_checkin c JOIN puma_eventi e ON e.id=c.evento_id
        LEFT JOIN puma_livelli l ON l.id=e.livello_id WHERE c.username=? ORDER BY e.data DESC""", (u["username"],)).fetchall()
    return render_template("puma/profilo.html", sc=scadenze(u=u["username"]), ind=ind, col=col)

@puma_bp.route("/settore/<cod>")
def settore(cod):
    u = current_user()
    if not settore_ok(u, cod): abort(403)
    s = db().execute("SELECT * FROM puma_settori WHERE codice=?", (cod,)).fetchone() or abort(404)
    liv = u["livello"]
    vede = settore_ok(u, cod, "gestore") or liv in ("regione", "nazionale")   # ROP del Comando, ROR della regione, Nazionale
    if liv == "nazionale": comandi = None
    elif liv == "regione":
        comandi = [r[0] for r in db().execute("SELECT comando_id FROM puma_comando_dir WHERE direzione_id=?", (u["direzione_id"],))]
    else: comandi = [u["comando_id"]]
    return render_template("puma/settore.html", s=s, rop=vede, livello=liv, sc=scadenze(settore=cod, comando=comandi) if vede else [])

@puma_bp.route("/livelli", methods=["GET", "POST"])
def livelli_utente():
    """Solo amministratori: livello di visibilità (comando / regione / nazionale) di ogni utente."""
    u = current_user()
    if u["ruolo"] != "ADMIN": abort(403)
    if request.method == "POST":
        for k, v in request.form.items():
            if k.startswith("l_") and v in ("comando", "regione", "nazionale"):
                db().execute("INSERT INTO puma_livello_utente(utente_id,livello) VALUES(?,?) ON CONFLICT(utente_id) DO UPDATE SET livello=excluded.livello", (int(k[2:]), v))
        db().commit(); flash("Livelli di visibilità salvati."); return redirect(url_for("puma.livelli_utente"))
    righe = db().execute("""SELECT u.id, u.email, u.nome, u.cognome, k.nome comando, d.nome direzione, COALESCE(l.livello,'comando') livello
        FROM utenti u LEFT JOIN comandi k ON k.id=u.comando_id LEFT JOIN puma_comando_dir cd ON cd.comando_id=u.comando_id
        LEFT JOIN puma_direzioni d ON d.id=cd.direzione_id LEFT JOIN puma_livello_utente l ON l.utente_id=u.id
        WHERE u.stato='attivo' ORDER BY u.cognome""").fetchall()
    return render_template("puma/livelli.html", righe=righe)

@puma_bp.route("/impostazioni", methods=["GET", "POST"])
def impostazioni():
    u = current_user()
    if not _puo("puma", "gestore"): abort(403)
    cid, f = u["comando_id"], request.form
    if request.method == "POST":
        a = f["azione"]
        if a == "mail":
            db().execute("DELETE FROM puma_destinatari WHERE comando_id=?", (cid,))
            for r in RUOLI_MAIL:
                for m in f.get(r, "").replace(";", ",").split(","):
                    if "@" in m: db().execute("INSERT OR IGNORE INTO puma_destinatari VALUES(?,?,?)", (cid, r, m.strip()))
            db().execute("INSERT OR REPLACE INTO puma_config VALUES(?,?,?)", (cid, "giorni_preavviso", f.get("preavviso", "30")))
        elif a == "livelli":
            for l in livelli(): db().execute("UPDATE puma_livelli SET mesi_validita=? WHERE id=?", (int(f.get(f"m{l['id']}", l["mesi_validita"])), l["id"]))
        elif a == "manovra" and f.get("nome", "").strip():
            db().execute("INSERT INTO puma_manovre(livello_id,nome) VALUES(?,?)", (f["livello_id"], f["nome"].strip()))
        elif a == "elimina_manovra":
            db().execute("DELETE FROM puma_manovre WHERE id=?", (f["id"],))
        db().commit(); flash("Impostazioni salvate."); return redirect(url_for("puma.impostazioni"))
    mails = {r: ", ".join(x["email"] for x in db().execute("SELECT email FROM puma_destinatari WHERE comando_id=? AND ruolo=?", (cid, r))) for r in RUOLI_MAIL}
    man = db().execute("SELECT m.*, l.nome livello FROM puma_manovre m JOIN puma_livelli l ON l.id=m.livello_id ORDER BY l.nome, m.ordine, m.id").fetchall()
    return render_template("puma/impostazioni.html", mails=mails, preavviso=cfg(cid, "giorni_preavviso", "30"), livelli=livelli(), man=man)

def invia_alert_scadenze():
    n = 0
    for c in db().execute("SELECT DISTINCT comando_id FROM puma_individuali UNION SELECT DISTINCT comando_origine FROM puma_checkin"):
        cid = c[0]; pre = int(cfg(cid, "giorni_preavviso", 30))
        rop = [r["email"] for r in db().execute("SELECT email FROM puma_destinatari WHERE comando_id=? AND ruolo='ROP'", (cid,))]
        for s in scadenze(comando=cid):
            if s["giorni"] > pre: continue
            if db().execute("SELECT 1 FROM puma_alert_inviati WHERE username=? AND livello_id=? AND scadenza=?", (s["username"], s["livello_id"], s["scadenza"])).fetchone(): continue
            dest = [m for m in [email_utente(s["username"])] + rop if m]
            if not dest: continue
            try:
                manda(dest, f"[P.U.M.A.] Scadenza {s['livello']} – {s['username']}",
                      f"{s['username']}: l'addestramento {s['livello']} ({s['settore']}) scade il {s['scadenza']} ({s['giorni']} giorni).")
                db().execute("INSERT INTO puma_alert_inviati VALUES(?,?,?)", (s["username"], s["livello_id"], s["scadenza"])); db().commit(); n += 1
            except Exception as x:
                current_app.logger.warning("alert P.U.M.A. non inviato: %s", x)
    return n


# ---------------- TILE DELLA MAPPA (proxy con cache) ----------------
# Il browser non chiama OpenStreetMap: il portale ha Referrer-Policy "same-origin" (nessun Referer verso l'esterno) e
# OSM risponde 403 senza Referer/User-Agent. Le tile passano dal server del portale, che le scarica con uno
# User-Agent identificativo e le tiene in cache su disco (data/puma_tiles). Funziona anche con un tile server interno.
TILE_UPSTREAM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_TTL = 7 * 86400

def tile_bytes(z, x, y):
    """Bytes PNG della tile (cache su disco 7 giorni; se il download fallisce usa la copia vecchia; None se assente)."""
    path = os.path.join(config.DATA_DIR, "puma_tiles", str(z), str(x), f"{y}.png")
    if not (os.path.exists(path) and time.time() - os.path.getmtime(path) < TILE_TTL):
        url = (conf("PUMA_TILE_URL") or TILE_UPSTREAM).format(z=z, x=x, y=y, s="a")
        req = urllib.request.Request(url, headers={"User-Agent": conf("PUMA_TILE_UA", "PUMA-VVF/1.0 (intranet Vigili del Fuoco)"),
                                                   "Referer": request.host_url})
        try:
            with urllib.request.urlopen(req, timeout=10) as r: data = r.read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "wb") as f: f.write(data)
            os.replace(path + ".tmp", path)
        except Exception as e:
            current_app.logger.warning("tile %s/%s/%s non scaricata: %s", z, x, y, e)
            if not os.path.exists(path): return None
    with open(path, "rb") as f: return f.read()

@puma_bp.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    current_user()
    if not (0 <= z <= 19 and 0 <= x < 2 ** z and 0 <= y < 2 ** z): abort(404)
    data = tile_bytes(z, x, y)
    if data is None: abort(404)
    return Response(data, mimetype="image/png", headers={"Cache-Control": "private, max-age=86400"})
