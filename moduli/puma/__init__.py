"""Modulo P.U.M.A. (Piattaforma Unificata Monitoraggio Addestramenti): è il modulo principale, si apre subito dopo il login.

Standard dei moduli (vedi moduli/_esempio e docs/SVILUPPO.md):
- espone MODULO (metadati) e bp (blueprint senza url_prefix: lo aggiunge il nucleo, qui /puma)
- il nucleo (app.py) controlla l'accesso al settore e fornisce puo(settore, livello)
- lo schema del db è in migrazioni/002…005 (applicate all'avvio)

"""
import os, sqlite3, uuid
from datetime import date
from flask import (Blueprint, current_app, g, session, render_template, request,
                   redirect, url_for, abort, flash, send_from_directory)
from werkzeug.utils import secure_filename

# ---------- METADATI MODULO (standard moduli, come _esempio) ----------
MODULO = dict(
    codice='puma',
    nome='P.U.M.A.',
    descrizione='Piattaforma Unificata Monitoraggio Addestramenti',
    settore='puma',
    settore_nome='Addestramenti',
    icona='🎯',
    logo='img/puma-logo.jpg',   # mostrato nell'elenco delle app al posto dell'icona
)

# ---------- BLUEPRINT (SENZA url_prefix: lo aggiunge il nucleo) ----------
bp = Blueprint(
    'puma', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/puma-static',
)

# Alias retro-compatibile: chi importa puma_bp continua a funzionare
puma_bp = bp

CATEGORIE = {
    "manuali-puma": "Manuali P.U.M.A.",
    "manuali-settore": "Manuali di settore",
    "circolari-settore": "Circolari di settore",
}
TIPI = ["Corso", "Mantenimento", "Retraining", "Addestramento di settore", "Altro"]


# ---------- ADATTATORE AL NUCLEO (g.utente / g.perm di app.py) ----------
_LIV = ['lettura', 'scrittura', 'gestore']

def _puo(settore, minimo='lettura'):
    """Stessa logica di puo() del nucleo: admin sempre, altrimenti livello sul settore."""
    u = g.get('utente')
    if not u: return False
    if u['is_admin']: return True
    l = (g.get('perm') or {}).get(settore.lower())
    return l in _LIV and _LIV.index(l) >= _LIV.index(minimo)

def _user_or_none():
    u = g.get('utente')
    if not u: return None
    nome = ((u['nome'] or '') + ' ' + (u['cognome'] or '')).strip() or u['email']
    d = get_db()
    r = d.execute("SELECT livello FROM puma_livello_utente WHERE utente_id=?", (u['id'],)).fetchone()
    z = d.execute("SELECT direzione_id FROM puma_comando_dir WHERE comando_id=?", (u['comando_id'],)).fetchone()
    return {'username': u['email'], 'nome': nome, 'ruolo': 'ADMIN' if u['is_admin'] else 'UTENTE',
            'livello': r['livello'] if r else 'comando', 'comando_id': u['comando_id'],
            'direzione_id': z['direzione_id'] if z else None}

def current_user():
    u = _user_or_none()
    if not u: abort(401)
    if not u['comando_id']: abort(403)   # il Comando serve per il filtro dei dati (tenancy)
    return u

def settore_ok(u, cod, minimo='lettura'):
    """Il sotto-settore P.U.M.A. (es. SAF) coincide con un settore del nucleo (codice minuscolo)."""
    return _puo(cod, minimo)

def email_utente(username):
    return username if "@" in username else None

def can_write(u):
    return _puo('puma', 'scrittura')

def conf(chiave, default=None):
    """Configurazione: app.config oppure variabile d'ambiente (PUMA_SMTP_HOST, PUMA_TILE_URL...)."""
    return current_app.config.get(chiave) or os.environ.get(chiave) or default

# ---------- DB (db unico di PUMA; schema in migrazioni/002_puma.sql) ----------
import config, db as portale_db

def get_db():
    if "puma_db" not in g:
        g.puma_db = portale_db.connect()
    return g.puma_db

@bp.teardown_app_request
def _close(_):
    d = g.pop("puma_db", None)
    if d: d.close()

TENANT = ""  # lo schema è in migrazioni/002_puma.sql

def docs_dir():
    p = os.path.join(config.DATA_DIR, "puma_docs"); os.makedirs(p, exist_ok=True); return p


# ---------- SCOPE (RBAC + tenancy) ----------
def scope_sql(u, a=""):
    p = a + "." if a else ""
    cond = f"({p}is_condiviso_nazionale=1 AND {p}is_blindato=0)"
    lv = u.get("livello", "comando")
    if lv == "nazionale":
        return f"{p}is_blindato=0 OR {p}comando_id=?", [u.get("comando_id", -1)]
    if lv == "regione":
        return f"({p}direzione_id=? AND {p}is_blindato=0) OR {p}comando_id=? OR {cond}", [u.get("direzione_id"), u.get("comando_id")]
    return f"{p}comando_id=? OR {cond}", [u.get("comando_id")]


def elenco(tab, u, extra="1=1", params=(), order="id DESC"):
    w, p = scope_sql(u)
    return get_db().execute(
        f"SELECT * FROM {tab} WHERE ({w}) AND {extra} ORDER BY {order}",
        [*p, *params]
    ).fetchall()


def tenant_vals(u):
    f = request.form
    return (u["comando_id"], u.get("direzione_id"),
            int(bool(f.get("is_blindato"))),
            int(bool(f.get("is_condiviso_nazionale")) and not f.get("is_blindato")))


@bp.app_template_filter("from_json")
def _fj(v):
    import json
    try:
        return json.loads(v or "[]")
    except ValueError:
        return []


@bp.context_processor
def _ctx():
    return {
        "tile_url": url_for("puma.tile", z=0, x=0, y=0).replace("/0/0/0.png", "/{z}/{x}/{y}.png"),
        "settori_all": get_db().execute("SELECT * FROM puma_settori").fetchall(),
        "nomi": {r["id"]: r["nome"] for r in get_db().execute("SELECT id, nome FROM comandi")},
        "categorie": CATEGORIE,
        "tipi": TIPI,
    }


# ---------- ROUTE ----------
@bp.route("/")
def index():
    u = current_user()
    oggi = date.today().isoformat()
    mie = [x for x in get_db().execute("SELECT * FROM puma_settori") if settore_ok(u, x["codice"])]
    return render_template(
        "puma/home.html",
        settori=mie,
        n_oggi=len(elenco("puma_eventi", u, "data=? AND stato!='chiuso'", (oggi,))),
        n_att=len(elenco("puma_attivita", u, "stato='attiva'")),
        scrivi=can_write(u),
    )


@bp.route("/attivita", methods=["GET", "POST"])
def attivita():
    u = current_user()
    if request.method == "POST":
        if not can_write(u):
            abort(403)
        f = request.form
        get_db().execute(
            """INSERT INTO puma_attivita(titolo,tipo,descrizione,data_inizio,data_fine,comando_id,direzione_id,
               is_blindato,is_condiviso_nazionale,creato_da) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (f["titolo"].strip(), f.get("tipo"), f.get("descrizione"),
             f.get("data_inizio"), f.get("data_fine"),
             *tenant_vals(u), u["username"]),
        )
        get_db().commit()
        flash("Attività salvata.")
        return redirect(url_for("puma.attivita"))
    return render_template("puma/attivita.html",
                           righe=elenco("puma_attivita", u, "stato='attiva'"),
                           scrivi=can_write(u))


@bp.route("/oggi", methods=["GET", "POST"])
def oggi():
    u = current_user()
    d = date.today().isoformat()
    if request.method == "POST":
        if not can_write(u):
            abort(403)
        f = request.form
        get_db().execute(
            """INSERT INTO puma_addestramenti(attivita_id,data,ora,luogo,tema,istruttore,partecipanti,comando_id,
               direzione_id,is_blindato,is_condiviso_nazionale,creato_da) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f.get("attivita_id") or None, f.get("data") or d, f.get("ora"),
             f.get("luogo"), f["tema"].strip(), f.get("istruttore"),
             f.get("partecipanti"), *tenant_vals(u), u["username"]),
        )
        get_db().commit()
        flash("Addestramento registrato.")
        return redirect(url_for("puma.oggi"))
    return render_template("puma/oggi.html",
                           righe=elenco("puma_addestramenti", u, "data=?", (d,), "ora"),
                           attivita=elenco("puma_attivita", u, "stato='attiva'"),
                           oggi=d, scrivi=can_write(u))


@bp.route("/documentazione/<cat>", methods=["GET", "POST"])
def documentazione(cat):
    if cat not in CATEGORIE:
        abort(404)
    u = current_user()
    if request.method == "POST":
        if not can_write(u):
            abort(403)
        fl = request.files.get("file")
        if not fl or not fl.filename:
            flash("Seleziona un file.")
            return redirect(request.url)
        nome = f"{uuid.uuid4().hex}_{secure_filename(fl.filename)}"
        fl.save(os.path.join(docs_dir(), nome))
        get_db().execute(
            """INSERT INTO puma_documenti(categoria,titolo,settore,filename,comando_id,direzione_id,
               is_blindato,is_condiviso_nazionale,creato_da) VALUES(?,?,?,?,?,?,?,?,?)""",
            (cat, request.form["titolo"].strip(), request.form.get("settore"),
             nome, *tenant_vals(u), u["username"]),
        )
        get_db().commit()
        flash("Documento caricato.")
        return redirect(request.url)
    return render_template("puma/documenti.html",
                           cat=cat,
                           righe=elenco("puma_documenti", u, "categoria=?", (cat,)),
                           scrivi=can_write(u))


@bp.route("/documento/<int:i>")
def scarica(i):
    u = current_user()
    w, p = scope_sql(u)
    r = get_db().execute(
        f"SELECT filename FROM puma_documenti WHERE id=? AND ({w})", [i, *p]
    ).fetchone()
    if not r:
        abort(404)
    return send_from_directory(docs_dir(), r["filename"],
                               download_name=r["filename"].split("_", 1)[1])


@bp.route("/archivio")
def archivio():
    u = current_user()
    return render_template("puma/archivio.html",
                           att=elenco("puma_attivita", u, "stato='archiviata'"),
                           add=elenco("puma_addestramenti", u,
                                      "data<?", (date.today().isoformat(),), "data DESC"),
                           scrivi=can_write(u))


@bp.route("/archivia/<int:i>", methods=["POST"])
def archivia(i):
    u = current_user()
    if not can_write(u):
        abort(403)
    get_db().execute(
        "UPDATE puma_attivita SET stato='archiviata' WHERE id=? AND comando_id=?",
        (i, u["comando_id"]),
    )
    get_db().commit()
    return redirect(url_for("puma.attivita"))


from . import addestramenti, piano  # noqa: E402,F401  (registra le route dei moduli)