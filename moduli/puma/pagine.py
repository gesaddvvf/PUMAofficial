"""Pagine aggiunte per allineare PUMA al sito gesaddvvf.github.io/PUMA: Presenze Odierne (Real Time),
Report Collettivo e Area Comando, catalogo della documentazione (file su Google Drive)."""
import json, os
from datetime import date
from flask import render_template, abort, url_for
from . import bp, current_user, get_db, elenco, settore_ok, scope_sql
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


def comandi_visibili(u):
    """Sedi di cui l'utente vede i report: None = tutte (Nazionale, amministratori); Direzione = sedi della Direzione; altrimenti la propria.
    Con i livelli di accesso v1.3: le sedi dei ruoli con capacità «report» (più la propria)."""
    from .ruoli import accessi
    if u['ruolo'] == 'ADMIN' or u['livello'] == 'nazionale': return None
    acc = accessi()
    if acc.righe:
        s = acc.sedi('report')
        if s is None: return None
        if s: return sorted(set(s) | {u['comando_id']})
    if u['livello'] == 'regione':
        return [r[0] for r in get_db().execute('SELECT comando_id FROM puma_comando_dir WHERE direzione_id=?', (u['direzione_id'],))]
    return [u['comando_id']]


def _enti(u):
    """Scelte del selettore «Comando / Direzione» nel perimetro dell'utente."""
    vis = comandi_visibili(u)
    sedi = get_db().execute("""SELECT k.id, k.nome, k.tipo, cd.direzione_id FROM comandi k LEFT JOIN puma_comando_dir cd ON cd.comando_id=k.id
        ORDER BY CASE k.tipo WHEN 'comando' THEN 0 WHEN 'direzione' THEN 1 ELSE 2 END, k.nome""").fetchall()
    sedi = [s for s in sedi if vis is None or s['id'] in vis]
    dirz = get_db().execute('SELECT * FROM puma_direzioni ORDER BY nome').fetchall()
    dids = {s['direzione_id'] for s in sedi}
    return sedi, [x for x in dirz if vis is None or x['id'] in dids]


def _perimetro(u):
    """Ente scelto (?ente=c12 / d3) → (descrizione, elenco id sedi o None)."""
    from flask import request
    sedi, dirz = _enti(u); vis = comandi_visibili(u)
    ente = request.args.get('ente') or (f"c{u['comando_id']}" if u['comando_id'] else '')
    if ente.startswith('d') and ente[1:].isdigit():
        did = int(ente[1:]); dz = next((x for x in dirz if x['id'] == did), None)
        if dz: return ente, f"Direzione {dz['nome']}", [s['id'] for s in sedi if s['direzione_id'] == did], sedi, dirz
    if ente.startswith('c') and ente[1:].isdigit():
        cid = int(ente[1:]); s = next((x for x in sedi if x['id'] == cid), None)
        if s: return ente, s['nome'], [cid], sedi, dirz
    if ente == 'tutti' and vis is None: return ente, 'Tutta Italia', None, sedi, dirz
    return f"c{u['comando_id']}", next((x['nome'] for x in sedi if x['id'] == u['comando_id']), 'il tuo Comando'), [u['comando_id']], sedi, dirz


@bp.route('/report-collettivo')
def report_collettivo():
    """Report Collettivo per tipologia (come reportcollettivo.html del sito): Comando o Direzione, tipologia, anno.
    Per ogni nominativo: corso in possesso, ore nel periodo, ore in collettivo, stato, manovre fatte e da fare."""
    from flask import request
    from . import libretto as L
    from .navigazione import permessi
    from flask import g, current_app
    u = current_user()
    if not permessi(g.utente, current_app.extensions['puo'])['report']: abort(403)
    ente, nome_ente, sedi_id, sedi, dirz = _perimetro(u)
    y = request.args.get('anno', type=int) or date.today().year
    cat = L.Catalogo(get_db())
    from .ruoli import accessi
    aree = accessi().aree('report') if accessi().righe else None
    tip = [t for t in cat.tip.values() if t['corso'] and (aree is None or (t['settore'] or '').upper() in aree)]
    tip.sort(key=lambda t: (t['ordine'], t['nome']))
    tid = request.args.get('tipologia', type=int) or (tip[0]['id'] if tip else None)
    tutti = request.args.get('tutti') == '1'
    righe = []
    for p in L.persone_ente(get_db(), sedi_id):
        lib = L.libretto(get_db(), p, y, cat)
        r = next((x for x in lib['corsi'] if x['t']['id'] == tid), None)
        if r or tutti: righe.append(dict(p=p, r=r))
    stat = dict(persone=len(righe), ok=sum(1 for x in righe if x['r'] and x['r']['stato'] == 'ok'), ko=sum(1 for x in righe if x['r'] and x['r']['stato'] == 'ko'),
                nd=sum(1 for x in righe if not x['r'] or x['r']['stato'] == 'nd'))
    return render_template('puma/report_collettivo.html', righe=righe, stat=stat, tip=tip, t=cat.tip.get(tid), y=y, ente=ente, nome_ente=nome_ente,
                           sedi=sedi, dirz=dirz, tutti=tutti, nazionale=comandi_visibili(u) is None)


@bp.route('/cruscotto-corsi')
def cruscotto():
    """Cruscotto dello stato dei corsi: per ogni tipologia quanti la possiedono e quanti sono in regola nell'anno (prima versione)."""
    from flask import request, g, current_app
    from . import libretto as L
    from .navigazione import permessi
    u = current_user()
    if not permessi(g.utente, current_app.extensions['puo'])['report']: abort(403)
    ente, nome_ente, sedi_id, sedi, dirz = _perimetro(u)
    y = request.args.get('anno', type=int) or date.today().year
    cat = L.Catalogo(get_db())
    from .ruoli import accessi
    aree = accessi().aree('report') if accessi().righe else None
    tab = {t['id']: dict(t=t, possesso=0, ok=0, ko=0, nd=0, senza=0, ore=0.0, manovre_fatte=0, manovre_tot=0) for t in cat.tip.values()
           if t['corso'] and (aree is None or (t['settore'] or '').upper() in aree)}
    persone = L.persone_ente(get_db(), sedi_id)
    for p in persone:
        for r in L.libretto(get_db(), p, y, cat)['corsi']:
            x = tab.get(r['t']['id'])
            if not x: continue
            if r['possesso']:
                x['possesso'] += 1; x[r['stato']] += 1
                x['manovre_fatte'] += len(r['fatte']); x['manovre_tot'] += len(r['t']['previste'])
            else: x['senza'] += 1
            x['ore'] += r['ore']
    righe = sorted([x for x in tab.values() if x['possesso'] or x['senza'] or x['t']['di_tutti']], key=lambda x: (x['t']['ordine'], x['t']['nome']))
    return render_template('puma/cruscotto.html', righe=righe, y=y, ente=ente, nome_ente=nome_ente, sedi=sedi, dirz=dirz, n_persone=len(persone),
                           nazionale=comandi_visibili(u) is None)


@bp.route('/area-comando')
def area_comando():
    """Area Comando: reportistica e gestione per ROP, ROR, Funzionario di settore e amministratori."""
    from flask import g, current_app
    u = current_user()
    perm = permessi(g.utente, current_app.extensions['puo'])
    return render_template('puma/area_comando.html', perm=perm, livello=u['livello'])


@bp.route('/oggi-addestramenti')
def attivita_oggi():
    """Attività · Addestramenti di oggi: quelli programmati per oggi (miei e, se aperti, degli altri Comandi) con «Mi aggiungo»;
    sotto, i prossimi programmati (ci si aggiunge il giorno stesso)."""
    from datetime import timedelta
    from .addestramenti import can_write
    from flask import g
    u = current_user(); d = get_db()
    oggi = date.today().isoformat(); fra7 = (date.today() + timedelta(days=7)).isoformat()
    w, p = scope_sql(u, 'e')
    def carica(filtro, par):
        return d.execute(f"""SELECT e.*, k.nome AS comando, l.nome AS tipologia_nome, l.chiave,
                (SELECT COUNT(*) FROM puma_checkin c WHERE c.evento_id=e.id) AS presenti,
                (SELECT 1 FROM puma_checkin c WHERE c.evento_id=e.id AND c.username=?) AS io
            FROM puma_eventi e LEFT JOIN comandi k ON k.id=e.comando_id LEFT JOIN puma_livelli l ON l.id=e.livello_id
            WHERE {filtro} AND (({w}) OR (e.is_blindato=0))
            ORDER BY e.data, (e.comando_id<>?), (COALESCE(e.direzione_id, -1)<>COALESCE(?, -2)), k.nome, e.ora_inizio, e.team""",
            [u['username'], *par, *p, u['comando_id'], u.get('direzione_id')]).fetchall()
    di_oggi = carica("e.data=? AND e.stato<>'chiuso'", (oggi,))
    prossimi = carica("e.data>? AND e.data<=?", (oggi, fra7))
    return render_template('puma/attivita_oggi.html', di_oggi=di_oggi, prossimi=prossimi, oggi=oggi, scrivi=can_write(u), mio_comando=u['comando_id'])


@bp.route('/piani-sicurezza')
def piani():
    """Attività · Piani di sicurezza: gli addestramenti del mio Comando da oggi in avanti (e degli ultimi 30 giorni) con lo stato del piano."""
    from datetime import timedelta
    from . import responsabile
    from .ruoli import accessi
    u = current_user()
    if not (accessi().puo('piano') or responsabile(u, {'comando_id': u['comando_id'], 'tipologia': ''})): abort(403)
    dal = (date.today() - timedelta(days=30)).isoformat()
    righe = get_db().execute("""SELECT e.*, l.nome AS tipologia_nome, l.chiave, (SELECT COUNT(*) FROM puma_checkin c WHERE c.evento_id=e.id) AS presenti
        FROM puma_eventi e LEFT JOIN puma_livelli l ON l.id=e.livello_id WHERE e.comando_id=? AND e.data>=? ORDER BY e.data, e.ora_inizio""",
        (u['comando_id'], dal)).fetchall()
    righe = [r for r in righe if responsabile(u, r)]
    return render_template('puma/piani.html', righe=righe, oggi=date.today().isoformat())


@bp.route('/importa-foglio', methods=['GET', 'POST'])
def importa_foglio():
    """Area Comando · Importa il foglio PUMA (.xlsx): Formazione, Manovre_PREVISTE, Elenco_Filtrato. Solo amministratori."""
    import tempfile
    from flask import request, flash, redirect, url_for, g
    from . import foglio
    from .corsi import tipologie
    u = current_user()
    if not g.utente['is_admin']: abort(403)
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or not f.filename.lower().endswith('.xlsx'):
            flash('Scegli il file .xlsx scaricato da Google (File → Scarica → Microsoft Excel).'); return redirect(request.url)
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'foglio.xlsx'); f.save(p)
            try:
                r = foglio.importa(get_db(), p); get_db().commit()
            except Exception as e:
                get_db().rollback(); flash(f'Import non riuscito: {str(e)[:200] or e.__class__.__name__}'); return redirect(request.url)
        import db as portale_db
        with portale_db.connect() as c: portale_db.audit(c, g.utente['email'], 'importa_foglio', str(r)[:200])
        flash(f"Importati: {r['tipologie']} tipologie ({r['nuove']} nuove), {r['manovre']} manovre previste"
              f"{', ' + str(r['manovre_senza_corso']) + ' manovre senza tipologia riconosciuta' if r['manovre_senza_corso'] else ''}, {r['persone']} persone con i corsi in possesso. Fogli letti: {', '.join(r['fogli']) or 'nessuno'}.")
        return redirect(request.url)
    righe = tipologie(get_db(), solo_corsi=True)
    n_man = {r[0]: r[1] for r in get_db().execute('SELECT livello_id, COUNT(*) FROM puma_manovre GROUP BY livello_id')}
    n_poss = get_db().execute('SELECT COUNT(*), MAX(importato_il) FROM puma_possesso_foglio').fetchone()
    return render_template('puma/importa_foglio.html', righe=righe, n_man=n_man, n_poss=n_poss)
