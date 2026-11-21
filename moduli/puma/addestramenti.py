"""Moduli P.U.M.A.: collettivi (workflow responsabile), individuali, interventi reali, mappa live, scadenze."""
import json, smtplib, ssl, urllib.request, urllib.parse
from calendar import monthrange
from datetime import date, datetime
from email.message import EmailMessage
from flask import g, render_template, request, redirect, url_for, flash, abort, jsonify, current_app
import os, re, time, sqlite3
from flask import send_file, Response
import config
from . import bp as puma_bp, current_user, can_write, get_db, scope_sql, elenco, tenant_vals, settore_ok, email_utente, conf, _puo, responsabile

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
    """Addestramento visibile: non riservato, del proprio Comando, aperto dal suo link d'invito o con la persona tra i previsti."""
    from flask import session
    invitati = [int(x) for x in (session.get("ev_invitati") or []) if str(x).isdigit()]
    r = db().execute("""SELECT * FROM puma_eventi WHERE id=? AND (is_blindato=0 OR comando_id=? OR id IN (%s)
        OR id IN (SELECT evento_id FROM puma_previsti WHERE email=?))""" % (",".join(map(str, invitati)) or "0"),
        (i, u["comando_id"], u["username"])).fetchone()
    return r or abort(404)


# ---------------- PRESENZA: IN TURNO / FUORI TURNO, ANTICIPO / POSTICIPO ----------------
VARIAZIONI_MIN = [15, 30, 45, 60, 90, 120, 180, 240]


def servizio_proposto(email, e):
    """'in_turno' se il turno della persona è in servizio all'inizio dell'addestramento (e non è di salto), altrimenti 'fuori_turno'."""
    import turni
    p = db().execute("SELECT turno, salto_turno FROM utenti WHERE email=?", (email,)).fetchone()
    if not p or not p["turno"]: return None
    try: quando = datetime.fromisoformat(f"{e['data']}T{e['ora_inizio'] or '08:00'}")
    except ValueError: return None
    st = turni.stato(p["turno"], p["salto_turno"], quando)
    return None if st is None else ("in_turno" if st == "in_turno" else "fuori_turno")


def leggi_servizio(f, suff=""):
    """(servizio, variazione, minuti) dal modulo, validati."""
    sv = f.get("servizio" + suff); sv = sv if sv in ("in_turno", "fuori_turno") else None
    va = f.get("variazione" + suff); va = va if va in ("anticipo", "posticipo") else None
    mi = f.get("variazione_min" + suff, type=int)
    mi = mi if va and mi in VARIAZIONI_MIN else None
    return sv, (va if mi else None), mi


# ---------------- PERSONE PREVISTE E LINK D'INVITO ----------------
def persone_sede(cid):
    """Personale attivo della sede, per scegliere le persone previste."""
    return db().execute("""SELECT id, email, nome, cognome, qualifica, distaccamento FROM utenti WHERE stato='attivo' AND comando_id=?
        ORDER BY cognome, nome""", (cid,)).fetchall()


def salva_previsti(eid, cid, emails, testo, chi, origine="responsabile"):
    """Aggiunge le persone previste: email scelte dall'elenco + «nome.cognome» scritti a mano (anche chi non è ancora in PUMA)."""
    from auth_imap import norm_email, estrai_nome_cognome
    tutte, errati = list(emails), []
    for x in re.split(r"[,;\s]+", testo or ""):
        if not x: continue
        e, err = norm_email(x)
        if err: errati.append(x)
        else: tutte.append(e)
    adesso = datetime.now().isoformat(timespec="seconds"); n = 0
    for e in dict.fromkeys(tutte):
        p = db().execute("SELECT nome, cognome, comando_id FROM utenti WHERE email=?", (e,)).fetchone()
        nome = f"{p['cognome']} {p['nome']}".strip() if p else " ".join(reversed(estrai_nome_cognome(e)))
        cur = db().execute("""INSERT OR IGNORE INTO puma_previsti(evento_id,email,nome,comando_id,origine,aggiunto_da,aggiunto_il) VALUES(?,?,?,?,?,?,?)""",
                           (eid, e, nome, p["comando_id"] if p else cid, origine, chi, adesso))
        n += cur.rowcount
    return n, errati


def link_invito(e):
    tok = e["invito_token"]
    if not tok:
        import secrets
        tok = secrets.token_hex(12)
        db().execute("UPDATE puma_eventi SET invito_token=? WHERE id=?", (tok, e["id"])); db().commit()
    from .aree import indirizzo_pubblico
    return indirizzo_pubblico() + url_for("puma.invito_addestramento", token=tok)


@puma_bp.route("/i/<token>")
def invito_addestramento(token):
    """Link d'invito di un addestramento: apre la scheda (anche se riservato) per segnarsi tra i previsti o registrarsi il giorno stesso."""
    from flask import session
    u = current_user()
    e = db().execute("SELECT * FROM puma_eventi WHERE invito_token=?", (token,)).fetchone()
    if not e: flash("Link d'invito non valido.", "danger"); return redirect(url_for("puma.attivita_oggi"))
    session["ev_invitati"] = list(dict.fromkeys((session.get("ev_invitati") or []) + [e["id"]]))[-50:]
    flash("Sei stato invitato a questo addestramento: segnati tra i previsti oppure, il giorno stesso, registrati.", "success")
    return redirect(url_for("puma.collettivo", i=e["id"]))


@puma_bp.post("/collettivi/<int:i>/previsto")
def previsto_io(i):
    """Mi segno (o mi tolgo) tra le persone previste."""
    u = current_user(); e = ev_get(i, u)
    if e["data"] < date.today().isoformat() or e["stato"] == "chiuso": abort(400)
    if request.form.get("azione") == "togli":
        db().execute("DELETE FROM puma_previsti WHERE evento_id=? AND email=? AND stato='previsto'", (i, u["username"]))
        flash("Non sei più tra i previsti.", "success")
    else:
        salva_previsti(i, u["comando_id"], [u["username"]], "", u["username"], "invito")
        flash("Sei tra i previsti: il giorno dell'addestramento conferma la presenza.", "success")
    db().commit(); return redirect(url_for("puma.collettivo", i=i))


@puma_bp.post("/collettivi/<int:i>/previsti")
def previsti(i):
    """Il responsabile aggiunge o toglie persone previste e, il giorno dell'addestramento, conferma presenti e assenti."""
    u, e = _resp(i); f = request.form; a = f.get("azione")
    if a == "aggiungi":
        n, errati = salva_previsti(i, e["comando_id"], f.getlist("previsti"), f.get("altri"), u["username"])
        flash(f"{n} persone aggiunte ai previsti." + (f" Non riconosciuti: {', '.join(errati)} (scrivi nome.cognome)." if errati else ""), "success" if not errati else "warning")
    elif a == "togli":
        db().execute("DELETE FROM puma_previsti WHERE evento_id=? AND email=? AND stato!='confermato'", (i, f.get("email")))
    elif a == "conferma":
        if e["data"] != date.today().isoformat(): flash("Le presenze si confermano il giorno dell'addestramento.", "danger"); return redirect(url_for("puma.collettivo", i=i))
        ruoli = {r["codice"] for r in ics_ruoli()}; ora = datetime.now().strftime("%H:%M"); n = 0
        for p in db().execute("SELECT * FROM puma_previsti WHERE evento_id=?", (i,)).fetchall():
            v = f.get("esito_" + p["email"])
            if v == "presente":
                r = f.get("ruolo_" + p["email"]); r = r if r in ruoli else "OPER"
                sv, va, mi = leggi_servizio(f, "_" + p["email"])
                db().execute("""INSERT INTO puma_checkin(evento_id,username,nome,comando_origine,ora,ruolo_ics,convalidato,servizio,variazione,variazione_min)
                    VALUES(?,?,?,?,?,?,1,?,?,?) ON CONFLICT(evento_id,username) DO UPDATE SET ruolo_ics=excluded.ruolo_ics, convalidato=1,
                    servizio=excluded.servizio, variazione=excluded.variazione, variazione_min=excluded.variazione_min""",
                    (i, p["email"], p["nome"], p["comando_id"], ora, r, sv, va, mi))
                db().execute("UPDATE puma_previsti SET stato='confermato' WHERE evento_id=? AND email=?", (i, p["email"])); n += 1
            elif v == "assente":
                db().execute("DELETE FROM puma_checkin WHERE evento_id=? AND username=?", (i, p["email"]))
                db().execute("UPDATE puma_previsti SET stato='assente' WHERE evento_id=? AND email=?", (i, p["email"]))
        db().execute("UPDATE puma_eventi SET stato='attivo' WHERE id=? AND stato='programmato'", (i,))
        flash(f"Presenze confermate: {n}. Le trovi già convalidate tra le presenze.", "success")
    db().commit(); return redirect(url_for("puma.collettivo", i=i) + "#previsti")
def cod_add(d, tipologia, team, comando_id, org_dr, data):
    """COD_ADD = TIPOLOGIA-SQUADRA-<SIGLA DIREZIONE><SIGLA COMANDO | DR>-AAAAMMGG  (es. SAF-ALFA-VENBL-20261006; se organizza la Direzione: SAF-ALFA-VENDR-...)."""
    r = d.execute("""SELECT k.sigla cmd, k.tipo, COALESCE(dz.sigla,'NAZ') dir FROM comandi k LEFT JOIN puma_comando_dir cd ON cd.comando_id=k.id
        LEFT JOIN puma_direzioni dz ON dz.id=cd.direzione_id WHERE k.id=?""", (comando_id,)).fetchone()
    sede = 'DR' if org_dr or r['tipo'] == 'direzione' else (r['cmd'] or 'XX')   # Direzione regionale: ...-VENDR-...; CON: ...-NAZCON-...
    return f"{tipologia.upper()}-{team.upper()}-{r['dir']}{sede}-{data.replace('-', '')}"

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

ORARI = [f"{h:02d}:{m:02d}" for h in range(5, 24) for m in (0, 30)]
FINALITA = ["Mantenimento", "Retraining", "Corso di formazione", "Esercitazione", "Verifica / esame", "Addestramento congiunto con altri enti"]
RV_ELI = ["Elisuperficie", "Campo sportivo", "Prato", "Piazzale", "Parcheggio", "Spiaggia / greto"]
RV_AMB = ["Parcheggio", "Piazzale", "Strada di accesso", "Sede VVF", "Ingresso dell'area"]
DURATE = [(30, "30 minuti"), (60, "1 ora"), (90, "1 ora e mezza"), (120, "2 ore"), (180, "3 ore"), (240, "4 ore"), (300, "5 ore"), (360, "6 ore"), (480, "8 ore"), (600, "10 ore"), (720, "12 ore")]


def _aree_programma(u):
    """Aree corsi in cui l'utente può programmare: tutte se ha il permesso generale."""
    from .ruoli import accessi, aree
    al = accessi().aree("programma")
    tutte = [r["codice"] for r in aree(db())]
    if al is None or (not accessi().righe and _puo("puma", "scrittura")): return tutte
    return [a for a in tutte if a in al]


def _dr_utente(u):
    """Direzione Regionale per cui l'utente può organizzare (ruolo «Direzione» con programmazione), altrimenti None."""
    from .ruoli import accessi, MATRICE
    acc = accessi()
    for a in acc.righe:
        if a["livello"] == "direzione" and "programma" in MATRICE.get(a["ruolo"], ()): return a["sede_id"]
    if acc.admin or (not acc.righe and _puo("puma", "scrittura")):
        r = db().execute("SELECT k.id FROM comandi k JOIN puma_comando_dir cd ON cd.comando_id=k.id WHERE k.tipo='direzione' AND cd.direzione_id=?",
                         (u.get("direzione_id"),)).fetchone()
        return r["id"] if r else None
    return None


@puma_bp.route("/api/team-occupati")
def api_team_occupati():
    u = current_user()
    return jsonify([r[0] for r in db().execute("SELECT team FROM puma_eventi WHERE data=? AND tipologia=? AND comando_id=?",
                                               (request.args.get("data", ""), request.args.get("area", "").upper(), u["comando_id"]))])


@puma_bp.route("/collettivi/nuovo", methods=["GET", "POST"])
def collettivo_nuovo():
    """Programmazione guidata: quasi tutto da elenchi (data, orari, area, corso, finalità, squadra, località, RV, visibilità)."""
    from .corsi import tipologie
    from .localita import visibili, salva_nuova, centro_sede, gruppi
    u = current_user()
    aree_ok = _aree_programma(u)
    if not aree_ok: abort(403)
    dr = _dr_utente(u)
    oggi = date.today()
    if request.method == "POST":
        f = request.form
        def errore(t):
            flash(t, "danger"); return redirect(request.url)
        try: giorno = date.fromisoformat(f.get("data", ""))
        except ValueError: return errore("Scegli la data dell'addestramento.")
        if not (oggi <= giorno <= add_months(oggi, 12)): return errore("La data deve essere tra oggi e i prossimi 12 mesi.")
        oi, of = f.get("ora_inizio"), f.get("ora_fine")
        if oi not in ORARI or of not in ORARI or of <= oi: return errore("Scegli ora di inizio e di fine dagli elenchi (la fine dopo l'inizio).")
        area = (f.get("area") or "").upper()
        if area not in aree_ok: abort(403)
        liv = db().execute("SELECT * FROM puma_livelli WHERE id=? AND attiva=1", (f.get("livello_id", type=int),)).fetchone()
        if not liv or (liv["settore"] or "").upper() != area: return errore("Scegli il corso dell'area indicata.")
        if f.get("finalita") not in FINALITA: return errore("Scegli la finalità dell'addestramento.")
        if f.get("team") not in TEAM: return errore("Scegli la squadra dall'elenco.")
        org_dr = 1 if f.get("organizza") == "dr" and dr else 0
        rv_d, amb_d = f.get("rv_descr") or None, f.get("amb_descr") or None
        if (rv_d and rv_d not in RV_ELI) or (amb_d and amb_d not in RV_AMB): return errore("Scegli il tipo di RV dagli elenchi.")
        manovre = [m["nome"] for m in db().execute("SELECT nome FROM puma_manovre WHERE livello_id IN (?, ?)", (liv["id"], liv["equivale_a"] or liv["id"]))]
        scelte = [m for m in f.getlist("manovre") if m in manovre]
        lid = f.get("localita")
        if lid == "nuova":
            nome_loc = (f.get("nome") or "").strip()
            if not nome_loc: return errore("Dai un nome alla nuova località.")
            if f.get("salva_localita"):
                lid, err = salva_nuova(db(), u, f, u["comando_id"])
                if err: return errore(err)
            else: lid = None
        else:
            lid = int(lid) if (lid or "").isdigit() else None
            ok = lid and any(r["id"] == lid for r in visibili(db(), u))
            if not ok: return errore("Scegli la località dall'elenco (o «Nuova località»).")
            nome_loc = db().execute("SELECT nome FROM puma_localita WHERE id=?", (lid,)).fetchone()[0]
        lat, lon = num(f.get("lat")), num(f.get("lon"))
        if lat is None or lon is None: return errore("Manca il punto dell'area addestrativa sulla mappa.")
        titolo = f"{liv['sigla'] or liv['nome']} – {nome_loc}"[:120]
        try:
            cod = cod_add(db(), area, f["team"], u["comando_id"], org_dr, giorno.isoformat())
            c = db().execute("""INSERT INTO puma_eventi(data,ora_inizio,ora_fine,org_dr,cod_add,tipologia,livello_id,team,titolo,manovre,descrizione,finalita,localita_id,
              lat,lon,rv_lat,rv_lon,rv_descr,amb_lat,amb_lon,amb_descr,responsabile,comando_id,direzione_id,is_blindato,is_condiviso_nazionale)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (giorno.isoformat(), oi, of, org_dr, cod, area, liv["id"], f["team"], titolo, json.dumps(scelte),
               (f.get("descrizione") or "").strip()[:500] or None, f["finalita"], lid,
               lat, lon, num(f.get("rv_lat")), num(f.get("rv_lon")), rv_d, num(f.get("amb_lat")), num(f.get("amb_lon")), amb_d,
               u["username"], *tenant_vals(u)))
        except sqlite3.IntegrityError:
            return errore("Esiste già un addestramento %s – squadra %s in quella data per il tuo Comando: scegli un'altra squadra." % (area, f["team"]))
        import secrets
        eid = c.lastrowid
        db().execute("UPDATE puma_eventi SET invito_token=? WHERE id=?", (secrets.token_hex(12), eid))
        n, errati = salva_previsti(eid, u["comando_id"], f.getlist("previsti"), f.get("altri"), u["username"])
        db().commit()
        flash("Addestramento pianificato" + (f" con {n} persone previste" if n else "") + ": il giorno stabilito compare in «Partecipa ad addestramento». "
              "Dalla scheda copi il link d'invito." + (f" Nominativi non riconosciuti: {', '.join(errati)}." if errati else ""), "success")
        return redirect(url_for("puma.collettivo", i=eid))
    from .localita import TIPI as TIPI_LOC
    centro = centro_sede(db(), u["comando_id"])
    return render_template("puma/collettivo_nuovo.html", team=TEAM, tipologie=tipologie(db(), solo_corsi=False, attive=True, aree=aree_ok),
                           aree=[r for r in db().execute("SELECT * FROM puma_settori WHERE attiva=1 ORDER BY ordine, nome") if r["codice"] in aree_ok],
                           oggi=oggi.isoformat(), giorno=request.args.get("data") or oggi.isoformat(), max_data=add_months(oggi, 12).isoformat(),
                           orari=ORARI, finalita=FINALITA, rv_eli=RV_ELI, rv_amb=RV_AMB, localita=gruppi(visibili(db(), u)), tipi_loc=TIPI_LOC,
                           centro=centro, centro_dr=centro_sede(db(), dr) if dr else None, dr=dr,
                           nome_dr=db().execute("SELECT nome FROM comandi WHERE id=?", (dr,)).fetchone()[0] if dr else None,
                           mio_comando=db().execute("SELECT nome FROM comandi WHERE id=?", (u["comando_id"],)).fetchone()[0],
                           persone=persone_sede(u["comando_id"]))

@puma_bp.route("/collettivi/<int:i>")
def collettivo(i):
    u = current_user(); e = ev_get(i, u)
    chk = db().execute("SELECT * FROM puma_checkin WHERE evento_id=? ORDER BY ora", (i,)).fetchall()
    mio = any(c["username"] == u["username"] for c in chk)
    prev = db().execute("SELECT * FROM puma_previsti WHERE evento_id=? ORDER BY stato='previsto' DESC, nome", (i,)).fetchall()
    resp = responsabile(u, e)
    io_previsto = next((p for p in prev if p["email"] == u["username"]), None)
    return render_template("puma/collettivo.html", e=e, chk=chk, mio=mio, resp=resp, previsti=prev, io_previsto=io_previsto,
                           abilitato=settore_ok(u, e["tipologia"]), ruoli=ics_ruoli(), oggi=date.today().isoformat(),
                           link=link_invito(e) if resp else None, persone=persone_sede(e["comando_id"]) if resp else [],
                           gia={p["email"] for p in prev} | {c["username"] for c in chk},
                           proposta={p["email"]: servizio_proposto(p["email"], e) for p in prev} if resp else {}, minuti=VARIAZIONI_MIN,
                           impianti=db().execute("SELECT id, titolo, stato FROM puma_impianti WHERE evento_id=?", (i,)).fetchall())

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
        sv, va, mi = leggi_servizio(request.form)
        if not sv and g.utente["tipo_utente"] != "esterno": flash("Indica se partecipi in turno o fuori turno."); return redirect(request.url)
        db().execute("""INSERT INTO puma_checkin(evento_id,username,nome,comando_origine,ora,ruolo_ics,servizio,variazione,variazione_min) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(evento_id,username) DO UPDATE SET ruolo_ics=excluded.ruolo_ics, servizio=excluded.servizio, variazione=excluded.variazione,
            variazione_min=excluded.variazione_min""", (i, u["username"], u.get("nome", u["username"]), u["comando_id"], datetime.now().strftime("%H:%M"), r, sv, va, mi))
        db().execute("UPDATE puma_eventi SET stato='attivo' WHERE id=? AND stato='programmato'", (i,))
        db().execute("UPDATE puma_previsti SET stato='confermato' WHERE evento_id=? AND email=?", (i, u["username"])); db().commit()
        flash("Registrazione effettuata.", "success"); return redirect(url_for("puma.collettivo", i=i))
    mio = db().execute("SELECT ruolo_ics FROM puma_checkin WHERE evento_id=? AND username=?", (i, u["username"])).fetchone()
    p = db().execute("SELECT codice_fiscale FROM puma_persone WHERE utente_id=?", (g.utente["id"],)).fetchone()
    ck = db().execute("SELECT * FROM puma_checkin WHERE evento_id=? AND username=?", (i, u["username"])).fetchone()
    return render_template("puma/partecipa.html", e=e, ruoli=ruoli, mio=mio["ruolo_ics"] if mio else None, cf=p["codice_fiscale"] if p else "",
                           servizio=(ck["servizio"] if ck and ck["servizio"] else servizio_proposto(u["username"], e)), ck=ck, minuti=VARIAZIONI_MIN)

def _resp(i):
    u = current_user(); e = ev_get(i, u)
    if not responsabile(u, e): abort(403)
    return u, e

@puma_bp.post("/collettivi/<int:i>/convalida")
def convalida(i):
    u, e = _resp(i); ids = request.form.getlist("ok")
    for r in db().execute("SELECT username FROM puma_checkin WHERE evento_id=?", (i,)).fetchall():
        v = request.form.get("ruolo_" + r["username"])
        if v: db().execute("UPDATE puma_checkin SET ruolo_ics=? WHERE evento_id=? AND username=?", (v, i, r["username"]))
        if request.form.get("servizio_" + r["username"]):
            sv, va, mi = leggi_servizio(request.form, "_" + r["username"])
            db().execute("UPDATE puma_checkin SET servizio=?, variazione=?, variazione_min=? WHERE evento_id=? AND username=?", (sv, va, mi, i, r["username"]))
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
    """Registrazione individuale guidata: solo i corsi in possesso (e le attività generiche), data entro 60 giorni, orari e durata da elenco."""
    from datetime import timedelta
    from .corsi import tipologie, possesso
    from .localita import visibili, gruppi
    u = current_user(); oggi = date.today()
    poss = possesso(db(), g.utente)
    esclusi = ("intervento", "piano di sicurezza mancante")   # gli interventi hanno la loro pagina; il «piano mancante» è un segnale del sito
    tip = [t for t in tipologie(db(), attive=True) if (t["id"] in poss or not t["corso"] or t["di_tutti"]) and t["nome"].split(" (")[0].strip().lower() not in esclusi]
    aree_mie = []
    for t in tip:
        if t["settore"] and t["settore"] not in [a["codice"] for a in aree_mie]:
            r = db().execute("SELECT * FROM puma_settori WHERE codice=? AND attiva=1", (t["settore"],)).fetchone()
            if r: aree_mie.append(r)
    aree_mie.sort(key=lambda a: (a["ordine"], a["nome"]))
    if request.method == "POST":
        f = request.form
        def errore(t):
            flash(t, "danger"); return redirect(url_for("puma.individuali"))
        liv = next((t for t in tip if t["id"] == f.get("livello_id", type=int)), None)
        if not liv: return errore("Scegli il corso tra quelli in tuo possesso.")
        try: giorno = date.fromisoformat(f.get("data", ""))
        except ValueError: return errore("Scegli la data.")
        if not (oggi - timedelta(days=60) <= giorno <= oggi): return errore("Si registrano attività degli ultimi 60 giorni (non future).")
        if f.get("ora") not in ORARI: return errore("Scegli l'ora di inizio dall'elenco.")
        durata = f.get("durata", type=int)
        if durata not in [d for d, _ in DURATE]: return errore("Scegli la durata dall'elenco.")
        inizio = datetime.fromisoformat(f"{giorno.isoformat()}T{f['ora']}")
        fine = inizio + timedelta(minutes=durata)
        if fine > datetime.now() + timedelta(minutes=5): return errore("L'attività non può finire nel futuro.")
        manovre = [m["nome"] for m in db().execute("SELECT nome FROM puma_manovre WHERE livello_id IN (?, ?)", (liv["id"], liv["equivale_a"] or liv["id"]))]
        lid = f.get("localita", type=int)
        if lid and not any(r["id"] == lid for r in visibili(db(), u)): lid = None
        db().execute("""INSERT INTO puma_individuali(username,tipologia,livello_id,inizio,fine,manovre,descrizione,localita_id,comando_id,direzione_id,is_blindato,
            is_condiviso_nazionale) VALUES(?,?,?,?,?,?,?,?,?,?,0,0)""", (u["username"], liv["settore"], liv["id"], inizio.isoformat(timespec="minutes"),
            fine.isoformat(timespec="minutes"), json.dumps([m for m in f.getlist("manovre") if m in manovre]), (f.get("descrizione") or "").strip()[:500] or None,
            lid, u["comando_id"], u.get("direzione_id")))
        db().commit(); flash("Attività individuale registrata: la trovi nel tuo Report individuale.", "success"); return redirect(url_for("puma.individuali"))
    mie = db().execute("""SELECT i.*, l.nome livello, lo.nome localita FROM puma_individuali i LEFT JOIN puma_livelli l ON l.id=i.livello_id
        LEFT JOIN puma_localita lo ON lo.id=i.localita_id WHERE username=? ORDER BY inizio DESC LIMIT 30""", (u["username"],)).fetchall()
    ora = datetime.now(); proposta = f"{max(5, ora.hour - 2):02d}:00"
    return render_template("puma/individuali.html", righe=mie, tipologie=tip, aree=aree_mie, oggi=oggi.isoformat(),
                           min_data=(oggi - timedelta(days=60)).isoformat(), orari=ORARI, durate=DURATE, proposta=proposta,
                           localita=gruppi(visibili(db(), u)), possesso=poss)

@puma_bp.route("/api/manovre/<int:lid>")
def api_manovre(lid):
    current_user()
    lid = db().execute("SELECT COALESCE(equivale_a, id) FROM puma_livelli WHERE id=?", (lid,)).fetchone() or [lid]
    # anche le (N): attività generiche (le ore contano) che si possono indicare, ma non sono manovre previste nel libretto
    return jsonify([dict(r) for r in db().execute("SELECT id,nome,ciclo,lettera FROM puma_manovre WHERE livello_id IN (?, ?) ORDER BY COALESCE(lettera,'')='N', ordine, id", (lid[0], request.view_args["lid"]))])

TIPI_INTERVENTO = ["Soccorso a persona", "Ricerca persona dispersa", "Recupero in ambiente impervio", "Soccorso in acqua", "Crollo / dissesto",
                   "Incendio", "Incidente stradale", "Sostanze pericolose", "Supporto ad altri enti", "Altro"]


@puma_bp.route("/interventi", methods=["GET", "POST"])
def interventi():
    """Interventi reali: area corsi tra quelle dei corsi in possesso, data non futura, tipo di intervento da elenco."""
    from datetime import timedelta
    from .corsi import possesso
    u = current_user(); oggi = date.today()
    poss = possesso(db(), g.utente)
    codici = {r["settore"] for r in db().execute("SELECT id, settore FROM puma_livelli") if r["id"] in poss}
    mie = [s for s in db().execute("SELECT * FROM puma_settori WHERE attiva=1 ORDER BY ordine, nome") if s["codice"] in codici] or \
          [s for s in db().execute("SELECT * FROM puma_settori WHERE attiva=1 ORDER BY ordine, nome") if settore_ok(u, s["codice"])]
    if request.method == "POST":
        f = request.form
        if f.get("macro") not in [s["codice"] for s in mie]: abort(403)
        try: giorno = date.fromisoformat(f.get("data", ""))
        except ValueError: giorno = None
        if not giorno or not (oggi - timedelta(days=365) <= giorno <= oggi):
            flash("Data non valida: l'intervento deve essere dell'ultimo anno e non futuro.", "danger"); return redirect(url_for("puma.interventi"))
        tipo = f.get("tipo") if f.get("tipo") in TIPI_INTERVENTO else "Altro"
        note = (f.get("descrizione") or "").strip()[:300]
        db().execute("""INSERT INTO puma_interventi(username,macro,data,descrizione,comando_id,direzione_id,is_blindato,is_condiviso_nazionale)
            VALUES(?,?,?,?,?,?,0,0)""", (u["username"], f["macro"], giorno.isoformat(), tipo + (f" – {note}" if note else ""), u["comando_id"], u.get("direzione_id")))
        db().commit(); flash("Intervento registrato.", "success"); return redirect(url_for("puma.interventi"))
    r = db().execute("SELECT * FROM puma_interventi WHERE username=? ORDER BY data DESC LIMIT 50", (u["username"],)).fetchall()
    return render_template("puma/interventi.html", righe=r, oggi=oggi.isoformat(), min_data=(oggi - timedelta(days=365)).isoformat(),
                           mie=mie, tipi=TIPI_INTERVENTO)

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
    """Report Individuale: libretto di formazione (come reportindividuale.html del sito). ?utente=<id> per ROP/ROR/Nazionale."""
    from .libretto import libretto
    from .pagine import comandi_visibili
    u = current_user(); anno = request.args.get("anno", type=int) or date.today().year
    chi = g.utente
    altro = request.args.get("utente", type=int)
    if altro and altro != g.utente["id"] and g.utente["tipo_utente"] == "esterno": abort(403)
    if altro and altro != g.utente["id"]:
        vis = comandi_visibili(u)
        chi = db().execute("SELECT u.*, k.nome AS comando FROM utenti u LEFT JOIN comandi k ON k.id=u.comando_id WHERE u.id=?", (altro,)).fetchone() or abort(404)
        if vis is not None and chi["comando_id"] not in vis: abort(403)
    lib = libretto(db(), chi, anno)
    return render_template("puma/libretto.html", lib=lib, chi=chi, y=anno, proprio=chi["id"] == g.utente["id"])

@puma_bp.route("/settore/<cod>")
def settore(cod):
    u = current_user()
    if not settore_ok(u, cod): abort(403)
    s = db().execute("SELECT * FROM puma_settori WHERE codice=UPPER(?)", (cod,)).fetchone() or abort(404)
    liv = u["livello"]
    vede = settore_ok(u, cod, "gestore") or liv in ("regione", "nazionale")   # ROP del Comando, ROR della regione, Nazionale
    if liv == "nazionale": comandi = None
    elif liv == "regione":
        comandi = [r[0] for r in db().execute("SELECT comando_id FROM puma_comando_dir WHERE direzione_id=?", (u["direzione_id"],))]
    else: comandi = [u["comando_id"]]
    return render_template("puma/settore.html", s=s, rop=vede, livello=liv, sc=scadenze(settore=cod, comando=comandi) if vede else [])

@puma_bp.route("/impostazioni", methods=["GET", "POST"])
def impostazioni():
    u = current_user()
    from .ruoli import accessi
    acc = accessi()
    if not (acc.puo("impostazioni", sede=u["comando_id"]) or (not acc.righe and _puo("puma", "gestore"))): abort(403)
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
    return render_template("puma/impostazioni.html", mails=mails, preavviso=cfg(cid, "giorni_preavviso", "30"), livelli=livelli(), man=man,
                           comando=db().execute("SELECT * FROM comandi WHERE id=?", (cid,)).fetchone())

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
