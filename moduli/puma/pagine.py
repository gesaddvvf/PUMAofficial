"""Pagine aggiunte per allineare PUMA al sito gesaddvvf.github.io/PUMA: Presenze Odierne (Real Time),
Report Collettivo e Area Comando, catalogo della documentazione (file su Google Drive)."""
import json, os
from datetime import date
from flask import render_template, abort, url_for
from . import bp, current_user, get_db, elenco, settore_ok
from .addestramenti import scadenze
from .navigazione import permessi

_CATALOGO = None


def catalogo(cat):
    """Elenco dei documenti condivisi su Google Drive, come nel sito P.U.M.A. (dati/documentazione.json)."""
    global _CATALOGO
    if _CATALOGO is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dati', 'documentazione.json'), encoding='utf-8') as f:
            _CATALOGO = json.load(f)
    return _CATALOGO.get(cat)


@bp.route('/presenze')
def presenze():
    """Real Time · Presenze Odierne: addestramenti collettivi di oggi e personale registrato (check-in)."""
    u = current_user()
    oggi = date.today().isoformat()
    eventi = elenco('puma_eventi', u, 'data=?', (oggi,), order='comando_id, ora_inizio, team')
    righe = []
    for e in eventi:
        pres = get_db().execute("""SELECT c.username, COALESCE(NULLIF(TRIM(COALESCE(ut.nome,'')||' '||COALESCE(ut.cognome,'')),''), c.nome, c.username) AS chi,
                c.ora, c.convalidato, c.ruolo_ics, k.nome AS comando
            FROM puma_checkin c LEFT JOIN utenti ut ON ut.email=c.username LEFT JOIN comandi k ON k.id=c.comando_origine
            WHERE c.evento_id=? ORDER BY c.ora""", (e['id'],)).fetchall()
        righe.append(dict(e=e, presenti=pres, convalidati=sum(1 for p in pres if p['convalidato'])))
    return render_template('puma/presenze.html', righe=righe, oggi=oggi, totale=sum(len(r['presenti']) for r in righe))


@bp.route('/report-collettivo')
def report_collettivo():
    """Report Collettivo: scadenze del personale per settore (ROP: Comando · ROR: regione · Nazionale: tutti)."""
    return _report(current_user())


def _report(u):
    liv = u['livello']
    if liv == 'nazionale': comandi, ambito = None, 'tutta Italia'
    elif liv == 'regione':
        comandi = [r[0] for r in get_db().execute('SELECT comando_id FROM puma_comando_dir WHERE direzione_id=?', (u['direzione_id'],))]
        ambito = 'la tua Direzione regionale'
    else: comandi, ambito = [u['comando_id']], 'il tuo Comando'
    sezioni = []
    for s in get_db().execute('SELECT * FROM puma_settori ORDER BY codice'):
        if not settore_ok(u, s['codice']): continue
        vede = settore_ok(u, s['codice'], 'gestore') or liv in ('regione', 'nazionale')
        if not vede: continue
        sc = scadenze(settore=s['codice'], comando=comandi)
        sezioni.append(dict(s=s, sc=sc, scadute=sum(1 for r in sc if r['giorni'] < 0), in_scadenza=sum(1 for r in sc if 0 <= r['giorni'] <= 60)))
    if not sezioni and not u['ruolo'] == 'ADMIN': abort(403)
    return render_template('puma/report_collettivo.html', sezioni=sezioni, ambito=ambito)


@bp.route('/area-comando')
def area_comando():
    """Area Comando: reportistica e gestione per ROP, ROR, Funzionario di settore e amministratori."""
    from flask import g, current_app
    u = current_user()
    perm = permessi(g.utente, current_app.extensions['puo'])
    return render_template('puma/area_comando.html', perm=perm, livello=u['livello'])
