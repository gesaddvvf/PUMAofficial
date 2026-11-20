"""Database località (v1.3): luoghi di addestramento con punto, RV elicottero e RV ambulanza, usati nei menu a comparsa
della programmazione e delle registrazioni. Le sedi dei Comandi (FireOps) e le sedi WAUC con coordinate sono caricate
in automatico; il resto lo inseriscono Amministratori, Funzionari, ROR/ROP e Staff (capacità «localita»)."""
from flask import render_template, request, redirect, url_for, flash, abort, jsonify, g
import db as portale_db
from . import bp, current_user, get_db
from . import ruoli as R

TIPI = [('sede', 'Sede VVF / distaccamento'), ('castello', 'Castello di manovra / torre'), ('aula', 'Aula / palestra'),
        ('parete', 'Parete rocciosa / falesia'), ('forra', 'Forra / torrente'), ('fiume', 'Fiume'), ('lago', 'Lago / bacino'),
        ('mare', 'Mare / costa'), ('grotta', 'Grotta / cavità'), ('macerie', 'Campo macerie / USAR'), ('edificio', 'Edificio / cantiere'),
        ('bosco', 'Bosco / area boscata'), ('area', 'Area aperta / campo'), ('altro', 'Altro')]
NOMI_TIPI = dict(TIPI)


def _f(v):
    try: return float(str(v).replace(',', '.'))
    except (TypeError, ValueError): return None


def carica_sedi(c):
    """Sedi centrali dei Comandi e sedi WAUC con coordinate come località (solo quelle che mancano)."""
    for k in c.execute("SELECT id, nome, tipo, comune, lat, lon FROM comandi WHERE lat IS NOT NULL AND lon IS NOT NULL").fetchall():
        lat, lon = _f(k['lat']), _f(k['lon'])
        if lat is None or lon is None: continue
        nome = 'Sede centrale' if k['tipo'] == 'comando' else 'Sede'
        c.execute("""INSERT OR IGNORE INTO puma_localita(nome, tipo, comune, comando_id, lat, lon, condivisa, origine, creato_da)
            VALUES(?, 'sede', ?, ?, ?, ?, 1, 'sede', 'PUMA')""", (nome, k['comune'], k['id'], lat, lon))
    try:
        for s in c.execute("""SELECT descrizione, comando_id, lat, lon, cod_tipo_dipartimento FROM sedi_wauc
                WHERE lat IS NOT NULL AND lon IS NOT NULL AND comando_id IS NOT NULL AND descrizione IS NOT NULL""").fetchall():
            c.execute("""INSERT OR IGNORE INTO puma_localita(nome, tipo, comando_id, lat, lon, condivisa, origine, creato_da)
                VALUES(?, 'sede', ?, ?, ?, 1, 'sede', 'WAUC')""", (s['descrizione'].strip().title()[:80], s['comando_id'], s['lat'], s['lon']))
    except Exception:
        pass


with portale_db.connect() as _c: carica_sedi(_c)


def visibili(d, u, sede=None, area=None):
    """Località attive che l'utente può scegliere: del suo Comando (o della sede indicata) e quelle condivise degli altri."""
    cid = sede or u['comando_id']
    righe = d.execute("""SELECT l.*, k.nome AS comando FROM puma_localita l JOIN comandi k ON k.id=l.comando_id
        WHERE l.attiva=1 AND (l.comando_id=? OR (l.condivisa=1 AND COALESCE(l.origine, '')<>'sede'))
        ORDER BY l.comando_id<>?, k.nome, l.tipo='sede' DESC, l.nome""", (cid, cid)).fetchall()
    if area: righe = [r for r in righe if not r['aree'] or area.upper() in r['aree'].upper().split(',')]
    return righe


def gruppi(righe):
    """[(nome sede, [località])] nell'ordine ricevuto (prima la propria sede)."""
    out = []
    for r in righe:
        if not out or out[-1][0] != r['comando']: out.append((r['comando'], []))
        out[-1][1].append(r)
    return out


def _puo(u, cid):
    return R.accessi().puo('localita', sede=cid)


@bp.route('/api/sedi')
def api_sedi():
    """Comandi, Direzioni, CON e SOCAV con coordinate, per «Centra la mappa su…»."""
    current_user()
    out = []
    for k in get_db().execute("SELECT id, nome, sigla, tipo, lat, lon FROM comandi ORDER BY CASE tipo WHEN 'comando' THEN 0 WHEN 'direzione' THEN 1 ELSE 2 END, nome"):
        lat, lon = _f(k['lat']), _f(k['lon'])
        if lat is not None and lon is not None: out.append(dict(id=k['id'], nome=k['nome'], tipo=k['tipo'], lat=lat, lon=lon))
    return jsonify(out)


@bp.route('/api/localita')
def api_localita():
    u = current_user()
    rr = visibili(get_db(), u, request.args.get('sede', type=int), request.args.get('area'))
    return jsonify([dict(id=r['id'], nome=r['nome'], tipo=r['tipo'], comando=r['comando'], comando_id=r['comando_id'], lat=r['lat'], lon=r['lon'],
                         rv_lat=r['rv_lat'], rv_lon=r['rv_lon'], rv_descr=r['rv_descr'], amb_lat=r['amb_lat'], amb_lon=r['amb_lon'],
                         amb_descr=r['amb_descr']) for r in rr])


def centro_sede(d, cid):
    """[lat, lon] della sede (per centrare le mappe sul Comando di appartenenza), None se non nota."""
    k = d.execute('SELECT lat, lon FROM comandi WHERE id=?', (cid,)).fetchone() if cid else None
    if k and _f(k['lat']) is not None and _f(k['lon']) is not None: return [_f(k['lat']), _f(k['lon'])]
    return None


def _dati(f):
    return dict(nome=f.get('nome', '').strip()[:80], tipo=f.get('tipo') if f.get('tipo') in NOMI_TIPI else 'altro',
                comune=f.get('comune', '').strip()[:60] or None, lat=_f(f.get('lat')), lon=_f(f.get('lon')),
                rv_lat=_f(f.get('rv_lat')), rv_lon=_f(f.get('rv_lon')), rv_descr=f.get('rv_descr', '').strip()[:120] or None,
                amb_lat=_f(f.get('amb_lat')), amb_lon=_f(f.get('amb_lon')), amb_descr=f.get('amb_descr', '').strip()[:120] or None,
                aree=','.join(sorted(set(f.getlist('aree')))) or None, note=f.get('note', '').strip()[:500] or None,
                condivisa=1 if f.get('condivisa') else 0)


def _valida(x):
    if not x['nome']: return 'Dai un nome alla località.'
    if x['lat'] is None or x['lon'] is None or not (-90 <= x['lat'] <= 90 and -180 <= x['lon'] <= 180): return 'Scegli il punto della località sulla mappa.'
    return None


def salva_nuova(d, u, f, cid):
    """Crea una località dai campi del modulo (usata anche dalla programmazione). Restituisce (id, errore)."""
    x = _dati(f); err = _valida(x)
    if err: return None, err
    if d.execute('SELECT 1 FROM puma_localita WHERE comando_id=? AND nome=?', (cid, x['nome'])).fetchone():
        return None, f"Esiste già una località «{x['nome']}» per questa sede."
    cur = d.execute('INSERT INTO puma_localita(' + ','.join(x) + ', comando_id, creato_da) VALUES(' + ','.join('?' * (len(x) + 2)) + ')',
                    (*x.values(), cid, u['username']))
    return cur.lastrowid, None


@bp.route('/localita', methods=['GET', 'POST'])
def localita():
    u = current_user(); d = get_db(); acc = R.accessi()
    sedi_ok = acc.sedi('localita')
    if sedi_ok == [] : abort(403)
    if request.method == 'POST':
        cid = request.form.get('comando_id', type=int) or u['comando_id']
        if not _puo(u, cid): abort(403)
        lid, err = salva_nuova(d, u, request.form, cid)
        if err: flash(err, 'danger'); return redirect(url_for('puma.localita'))
        portale_db.audit(d, u['username'], 'localita_creata', f"{lid} {request.form.get('nome')}")
        d.commit(); flash('Località salvata.', 'success'); return redirect(url_for('puma.localita', sede=cid))
    carica_sedi(d); d.commit()
    sede = request.args.get('sede', type=int) or u['comando_id']
    tipo = request.args.get('tipo', '')
    righe = [r for r in d.execute("""SELECT l.*, k.nome AS comando FROM puma_localita l JOIN comandi k ON k.id=l.comando_id
        WHERE l.comando_id=? ORDER BY l.attiva DESC, l.tipo='sede' DESC, l.nome""", (sede,)) if not tipo or r['tipo'] == tipo]
    sedi = [s for s in d.execute("SELECT id, nome, tipo FROM comandi ORDER BY CASE tipo WHEN 'comando' THEN 0 WHEN 'direzione' THEN 1 ELSE 2 END, nome")
            if sedi_ok is None or s['id'] in sedi_ok]
    return render_template('puma/localita.html', righe=righe, sede=sede, sedi=sedi, tipi=TIPI, nomi_tipi=NOMI_TIPI, tipo=tipo,
                           aree=R.aree(d), centro=centro_sede(d, sede), modifica=_puo(u, sede))


@bp.route('/localita/<int:i>', methods=['GET', 'POST'])
def localita_scheda(i):
    u = current_user(); d = get_db()
    r = d.execute('SELECT l.*, k.nome AS comando FROM puma_localita l JOIN comandi k ON k.id=l.comando_id WHERE l.id=?', (i,)).fetchone() or abort(404)
    modifica = _puo(u, r['comando_id'])
    if request.method == 'POST':
        if not modifica: abort(403)
        a = request.form.get('azione')
        if a == 'attiva':
            d.execute('UPDATE puma_localita SET attiva=1-attiva WHERE id=?', (i,))
        else:
            x = _dati(request.form); err = _valida(x)
            if err: flash(err, 'danger'); return redirect(request.url)
            d.execute('UPDATE puma_localita SET ' + ','.join(f'{k}=?' for k in x) + ' WHERE id=?', (*x.values(), i))
        d.commit(); flash('Località aggiornata.', 'success'); return redirect(url_for('puma.localita_scheda', i=i))
    usi = d.execute('SELECT COUNT(*) FROM puma_eventi WHERE localita_id=?', (i,)).fetchone()[0]
    return render_template('puma/localita_scheda.html', r=r, tipi=TIPI, aree=R.aree(d), modifica=modifica, usi=usi,
                           aree_sel=(r['aree'] or '').split(','))
