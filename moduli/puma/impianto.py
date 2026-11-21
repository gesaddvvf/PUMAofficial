"""Documento d'impianto dell'addestramento (v1.5): Attività → Documento d'impianto → «+ Crea».

Un documento ha titolo, area corsi, collegamento facoltativo a un addestramento pianificato, le DATE E ORARI e tante
SEZIONI con titolo personalizzabile: testo, una mappa (punto, RV elicottero, RV ambulanza) e immagini allegate.
Si stampa (o si salva in PDF dal browser) dalla pagina «Stampa»."""
import os, uuid
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, abort, send_from_directory, g
import config
from . import bp, current_user, get_db
from . import ruoli as R
from .addestramenti import ORARI, num

TITOLI = ['Premessa', 'Obiettivi', 'Scenario', 'Area addestrativa', 'Organizzazione', 'Risorse e mezzi', 'Attrezzature', 'Sicurezza',
          'Comunicazioni', 'Sanitario', 'Logistica', 'Cronoprogramma', 'Valutazione', 'Note']
SEZIONI_INIZIALI = ['Premessa e obiettivi', 'Scenario e area addestrativa', 'Organizzazione e risorse', 'Sicurezza', 'Comunicazioni']
FIRME = {b'\xff\xd8\xff': 'jpg', b'\x89PNG': 'png', b'GIF8': 'gif'}
MAX_IMMAGINE = 10 * 1024 * 1024


def cartella(iid):
    p = os.path.join(config.DATA_DIR, 'puma_impianti', str(iid)); os.makedirs(p, exist_ok=True); return p


def _doc(iid):
    r = get_db().execute('SELECT i.*, k.nome AS comando FROM puma_impianti i LEFT JOIN comandi k ON k.id=i.comando_id WHERE i.id=?', (iid,)).fetchone()
    return r or abort(404)


def puo_modificare(u, d):
    acc = R.accessi()
    return acc.admin or acc.puo('programma', d['area'] or None, sede=d['comando_id']) or (d['creato_da'] == u['username'] and acc.puo('programma'))


def puo_vedere(u, d):
    if puo_modificare(u, d) or d['comando_id'] == u['comando_id']: return True
    vis = R.accessi().sedi('report')
    return vis is None or (vis and d['comando_id'] in vis)


def _tocca(iid):
    get_db().execute('UPDATE puma_impianti SET aggiornato_il=? WHERE id=?', (datetime.now().isoformat(timespec='seconds'), iid))


def _parti(iid):
    d = get_db()
    date_ = d.execute('SELECT * FROM puma_impianti_date WHERE impianto_id=? ORDER BY data, ora_inizio', (iid,)).fetchall()
    sez = d.execute('SELECT * FROM puma_impianti_sezioni WHERE impianto_id=? ORDER BY ordine, id', (iid,)).fetchall()
    img = {}
    for r in d.execute('SELECT m.* FROM puma_impianti_immagini m JOIN puma_impianti_sezioni s ON s.id=m.sezione_id WHERE s.impianto_id=? ORDER BY m.id', (iid,)):
        img.setdefault(r['sezione_id'], []).append(r)
    return date_, sez, img


@bp.route('/impianti')
def impianti():
    u = current_user(); d = get_db(); acc = R.accessi()
    vis = acc.sedi('report')
    q = """SELECT i.*, k.nome AS comando, e.cod_add, (SELECT MIN(data) FROM puma_impianti_date x WHERE x.impianto_id=i.id) AS dal,
           (SELECT MAX(data) FROM puma_impianti_date x WHERE x.impianto_id=i.id) AS al, (SELECT COUNT(*) FROM puma_impianti_sezioni s WHERE s.impianto_id=i.id) AS n_sez
           FROM puma_impianti i LEFT JOIN comandi k ON k.id=i.comando_id LEFT JOIN puma_eventi e ON e.id=i.evento_id"""
    righe = [r for r in d.execute(q + ' ORDER BY COALESCE(i.aggiornato_il, i.creato_il) DESC').fetchall()
             if acc.admin or r['comando_id'] == u['comando_id'] or vis is None or (vis and r['comando_id'] in vis)]
    aree = [a for a in R.aree(d) if acc.puo('programma', a['codice'])]
    eventi = d.execute("""SELECT id, data, cod_add, titolo FROM puma_eventi WHERE comando_id=? AND data>=? ORDER BY data, ora_inizio""",
                       (u['comando_id'], (date.today() - timedelta(days=30)).isoformat())).fetchall()
    return render_template('puma/impianti.html', righe=righe, crea=bool(aree), aree=aree, eventi=eventi,
                           evento_sel=request.args.get('evento', type=int))


@bp.post('/impianti/nuovo')
def impianto_nuovo():
    u = current_user(); d = get_db(); f = request.form
    area = (f.get('area') or '').upper() or None
    if not R.accessi().puo('programma', area): abort(403)
    titolo = (f.get('titolo') or '').strip()[:150]
    if not titolo: flash("Dai un titolo al documento d'impianto.", 'danger'); return redirect(url_for('puma.impianti'))
    ev = f.get('evento_id', type=int)
    e = d.execute('SELECT * FROM puma_eventi WHERE id=? AND comando_id=?', (ev, u['comando_id'])).fetchone() if ev else None
    adesso = datetime.now().isoformat(timespec='seconds')
    iid = d.execute('INSERT INTO puma_impianti(titolo, area, evento_id, comando_id, creato_da, creato_il, aggiornato_il) VALUES(?,?,?,?,?,?,?)',
                    (titolo, area or (e['tipologia'] if e else None), e['id'] if e else None, u['comando_id'], u['username'], adesso, adesso)).lastrowid
    if e: d.execute('INSERT INTO puma_impianti_date(impianto_id, data, ora_inizio, ora_fine) VALUES(?,?,?,?)', (iid, e['data'], e['ora_inizio'], e['ora_fine']))
    for n, t in enumerate(SEZIONI_INIZIALI):
        d.execute('INSERT INTO puma_impianti_sezioni(impianto_id, ordine, titolo, mappa, lat, lon, rv_lat, rv_lon, amb_lat, amb_lon) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (iid, n, t, 1 if (n == 1 and e and e['lat']) else 0, *((e['lat'], e['lon'], e['rv_lat'], e['rv_lon'], e['amb_lat'], e['amb_lon']) if n == 1 and e else (None,) * 6)))
    d.commit(); flash("Documento creato: completa date, orari e sezioni (i titoli si possono cambiare).", 'success')
    return redirect(url_for('puma.impianto', i=iid))


@bp.route('/impianti/<int:i>', methods=['GET', 'POST'])
def impianto(i):
    u = current_user(); d = get_db(); doc = _doc(i)
    if not puo_vedere(u, doc): abort(403)
    mod = puo_modificare(u, doc)
    if request.method == 'POST':
        if not mod: abort(403)
        f = request.form; a = f.get('azione'); ancora = ''
        if a == 'testata':
            ev = f.get('evento_id', type=int)
            e = d.execute('SELECT id FROM puma_eventi WHERE id=? AND comando_id=?', (ev, doc['comando_id'])).fetchone() if ev else None
            d.execute('UPDATE puma_impianti SET titolo=?, evento_id=?, stato=? WHERE id=?',
                      ((f.get('titolo') or doc['titolo']).strip()[:150], e['id'] if e else None, 'definitivo' if f.get('stato') == 'definitivo' else 'bozza', i))
        elif a == 'data':
            try: giorno = date.fromisoformat(f.get('data', ''))
            except ValueError: giorno = None
            oi, of = f.get('ora_inizio'), f.get('ora_fine')
            if not giorno or oi not in ORARI or of not in ORARI or of <= oi: flash('Indica data, ora di inizio e di fine (la fine dopo l\'inizio).', 'danger')
            else: d.execute('INSERT INTO puma_impianti_date(impianto_id, data, ora_inizio, ora_fine, nota) VALUES(?,?,?,?,?)',
                            (i, giorno.isoformat(), oi, of, (f.get('nota') or '').strip()[:120] or None))
            ancora = '#date'
        elif a == 'togli_data':
            d.execute('DELETE FROM puma_impianti_date WHERE id=? AND impianto_id=?', (f.get('id', type=int), i)); ancora = '#date'
        elif a == 'sezione':
            o = (d.execute('SELECT MAX(ordine) FROM puma_impianti_sezioni WHERE impianto_id=?', (i,)).fetchone()[0] or 0) + 1
            sid = d.execute('INSERT INTO puma_impianti_sezioni(impianto_id, ordine, titolo) VALUES(?,?,?)',
                            (i, o, (f.get('titolo') or 'Nuova sezione').strip()[:120])).lastrowid
            ancora = f'#sez-{sid}'
        else:
            sid = f.get('sezione', type=int)
            s = d.execute('SELECT * FROM puma_impianti_sezioni WHERE id=? AND impianto_id=?', (sid, i)).fetchone() or abort(404)
            ancora = f'#sez-{sid}'
            if a == 'salva_sezione':
                mappa = 1 if f.get('mappa') else 0
                d.execute("""UPDATE puma_impianti_sezioni SET titolo=?, testo=?, mappa=?, lat=?, lon=?, rv_lat=?, rv_lon=?, amb_lat=?, amb_lon=? WHERE id=?""",
                          ((f.get('titolo') or s['titolo']).strip()[:120], (f.get('testo') or '').strip()[:20000] or None, mappa,
                           num(f.get('lat')), num(f.get('lon')), num(f.get('rv_lat')), num(f.get('rv_lon')), num(f.get('amb_lat')), num(f.get('amb_lon')), sid))
                flash('Sezione salvata.', 'success')
            elif a in ('su', 'giu'):
                tutte = d.execute('SELECT id FROM puma_impianti_sezioni WHERE impianto_id=? ORDER BY ordine, id', (i,)).fetchall()
                ids = [r[0] for r in tutte]; k = ids.index(sid); j = k - 1 if a == 'su' else k + 1
                if 0 <= j < len(ids):
                    ids[k], ids[j] = ids[j], ids[k]
                    for n, x in enumerate(ids): d.execute('UPDATE puma_impianti_sezioni SET ordine=? WHERE id=?', (n, x))
            elif a == 'togli_sezione':
                for m in d.execute('SELECT file FROM puma_impianti_immagini WHERE sezione_id=?', (sid,)).fetchall():
                    try: os.remove(os.path.join(cartella(i), m['file']))
                    except OSError: pass
                d.execute('DELETE FROM puma_impianti_sezioni WHERE id=?', (sid,)); ancora = ''
            elif a == 'immagine':
                fl = request.files.get('file')
                dati = fl.read(MAX_IMMAGINE + 1) if fl else b''
                ext = next((e for k, e in FIRME.items() if dati.startswith(k)), None)
                if not ext and dati[:4] == b'RIFF' and dati[8:12] == b'WEBP': ext = 'webp'
                if not dati: flash('Scegli un\'immagine.', 'danger')
                elif len(dati) > MAX_IMMAGINE: flash('Immagine troppo grande (massimo 10 MB).', 'danger')
                elif not ext: flash('Formato non riconosciuto: usa JPG, PNG, GIF o WEBP.', 'danger')
                else:
                    nome = f'{uuid.uuid4().hex}.{ext}'
                    with open(os.path.join(cartella(i), nome), 'wb') as out: out.write(dati)
                    d.execute('INSERT INTO puma_impianti_immagini(sezione_id, file, nome, didascalia, caricato_il) VALUES(?,?,?,?,?)',
                              (sid, nome, os.path.basename(fl.filename or nome)[:120], (f.get('didascalia') or '').strip()[:200] or None,
                               datetime.now().isoformat(timespec='seconds')))
                    flash('Immagine allegata.', 'success')
            elif a == 'togli_immagine':
                m = d.execute('SELECT * FROM puma_impianti_immagini WHERE id=? AND sezione_id=?', (f.get('id', type=int), sid)).fetchone()
                if m:
                    try: os.remove(os.path.join(cartella(i), m['file']))
                    except OSError: pass
                    d.execute('DELETE FROM puma_impianti_immagini WHERE id=?', (m['id'],))
        _tocca(i); d.commit()
        return redirect(url_for('puma.impianto', i=i) + ancora)
    date_, sez, img = _parti(i)
    eventi = d.execute("""SELECT id, data, cod_add, titolo FROM puma_eventi WHERE comando_id=? AND (data>=? OR id=?) ORDER BY data, ora_inizio""",
                       (doc['comando_id'], (date.today() - timedelta(days=30)).isoformat(), doc['evento_id'] or 0)).fetchall()
    from .localita import centro_sede
    return render_template('puma/impianto.html', doc=doc, date_=date_, sez=sez, img=img, mod=mod, orari=ORARI, titoli=TITOLI, eventi=eventi,
                           centro=centro_sede(d, doc['comando_id']), oggi=date.today().isoformat())


@bp.route('/impianti/<int:i>/stampa')
def impianto_stampa(i):
    u = current_user(); doc = _doc(i)
    if not puo_vedere(u, doc): abort(403)
    date_, sez, img = _parti(i)
    ev = get_db().execute('SELECT * FROM puma_eventi WHERE id=?', (doc['evento_id'],)).fetchone() if doc['evento_id'] else None
    return render_template('puma/impianto_stampa.html', doc=doc, date_=date_, sez=sez, img=img, ev=ev, adesso=datetime.now())


@bp.route('/impianti/<int:i>/immagini/<nome>')
def impianto_immagine(i, nome):
    u = current_user(); doc = _doc(i)
    if not puo_vedere(u, doc): abort(403)
    if not get_db().execute('SELECT 1 FROM puma_impianti_immagini m JOIN puma_impianti_sezioni s ON s.id=m.sezione_id WHERE s.impianto_id=? AND m.file=?',
                            (i, nome)).fetchone(): abort(404)
    return send_from_directory(cartella(i), nome, max_age=3600)


@bp.post('/impianti/<int:i>/elimina')
def impianto_elimina(i):
    import shutil
    u = current_user(); doc = _doc(i)
    if not puo_modificare(u, doc): abort(403)
    get_db().execute('DELETE FROM puma_impianti WHERE id=?', (i,)); get_db().commit()
    shutil.rmtree(cartella(i), ignore_errors=True)
    flash("Documento d'impianto eliminato.", 'success'); return redirect(url_for('puma.impianti'))
