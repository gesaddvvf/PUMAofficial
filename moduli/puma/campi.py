"""Campi personalizzabili del profilo per sede (v1.5).

Trento, Bolzano e Aosta hanno Corpi propri e non sono in WAUC: per queste sedi (comandi.profilo_libero = 1) qualifica e
distaccamento si scrivono liberamente e si aggiungono campi del profilo decisi dall'amministratore (Corpo di appartenenza,
matricola…). La stessa funzione si può attivare per qualunque sede da Area Comando → Campi personalizzati."""
import datetime
from flask import render_template, request, redirect, url_for, flash, abort
from . import bp, current_user, get_db
from . import ruoli as R

TIPI = [('testo', 'Testo'), ('elenco', 'Elenco a comparsa'), ('data', 'Data'), ('numero', 'Numero')]


def campi_di(c, cid, solo_attivi=True):
    return c.execute('SELECT * FROM puma_campi_sede WHERE comando_id=?' + (' AND attivo=1' if solo_attivi else '') + ' ORDER BY ordine, id',
                     (cid,)).fetchall()


def tutti_i_campi(c):
    """{comando_id: [campi attivi]} per il profilo (i campi compaiono quando si sceglie quella sede)."""
    out = {}
    for r in c.execute('SELECT * FROM puma_campi_sede WHERE attivo=1 ORDER BY ordine, id'):
        out.setdefault(r['comando_id'], []).append(r)
    return out


def valori(c, uid):
    return {r['campo_id']: r['valore'] for r in c.execute('SELECT * FROM puma_valori_campi WHERE utente_id=?', (uid,))}


def opzioni(campo):
    return [x.strip() for x in (campo['opzioni'] or '').splitlines() if x.strip()]


def leggi_valori(c, cid, form):
    """Valida i campi della sede scelta: ({campo_id: valore}, errore)."""
    out = {}
    for k in campi_di(c, cid):
        v = (form.get(f"campo_{k['id']}") or '').strip()[:200]
        if k['tipo'] == 'elenco' and v and v not in opzioni(k): return None, f"{k['etichetta']}: scegli un valore dell'elenco."
        if k['tipo'] == 'data' and v:
            try: datetime.date.fromisoformat(v)
            except ValueError: return None, f"{k['etichetta']}: data non valida."
        if k['tipo'] == 'numero' and v and not v.replace(',', '.').replace('.', '', 1).isdigit(): return None, f"{k['etichetta']}: atteso un numero."
        if k['obbligatorio'] and not v: return None, f"{k['etichetta']} è obbligatorio."
        out[k['id']] = v or None
    return out, None


def salva_valori(c, uid, cid, vals):
    c.execute('DELETE FROM puma_valori_campi WHERE utente_id=? AND campo_id NOT IN (SELECT id FROM puma_campi_sede WHERE comando_id=?)', (uid, cid))
    for k, v in vals.items():
        c.execute('INSERT INTO puma_valori_campi(utente_id, campo_id, valore) VALUES(?,?,?) ON CONFLICT(utente_id, campo_id) DO UPDATE SET valore=excluded.valore',
                  (uid, k, v))


def campi_utente(c, utente):
    """[(etichetta, valore)] dei campi personalizzati compilati, per Area personale e scheda utente."""
    return [(r['etichetta'], r['valore']) for r in c.execute("""SELECT k.etichetta, v.valore FROM puma_valori_campi v JOIN puma_campi_sede k ON k.id=v.campo_id
        WHERE v.utente_id=? AND k.attivo=1 AND v.valore IS NOT NULL ORDER BY k.ordine, k.id""", (utente['id'],))]


@bp.route('/campi-personalizzati', methods=['GET', 'POST'])
def campi_personalizzati():
    u = current_user(); d = get_db(); acc = R.accessi()
    sedi_ok = acc.sedi('impostazioni')
    if sedi_ok == []: abort(403)
    sedi = [s for s in d.execute("SELECT id, nome, sigla, tipo, profilo_libero FROM comandi ORDER BY profilo_libero DESC, CASE tipo WHEN 'comando' THEN 0 WHEN 'direzione' THEN 1 ELSE 2 END, nome")
            if sedi_ok is None or s['id'] in sedi_ok]
    ids = {s['id'] for s in sedi}
    sede = request.values.get('sede', type=int) or next((s['id'] for s in sedi if s['profilo_libero']), u['comando_id'])
    if sede not in ids: abort(403)
    if request.method == 'POST':
        f = request.form; a = f.get('azione')
        if a == 'libero':
            d.execute('UPDATE comandi SET profilo_libero=? WHERE id=?', (1 if f.get('profilo_libero') else 0, sede))
            flash('Impostazione del profilo salvata.', 'success')
        elif a == 'nuovo':
            et = f.get('etichetta', '').strip()[:80]; tipo = f.get('tipo') if f.get('tipo') in dict(TIPI) else 'testo'
            if not et: flash('Scrivi il nome del campo.', 'danger')
            elif tipo == 'elenco' and not f.get('opzioni', '').strip(): flash('Per un elenco scrivi le voci, una per riga.', 'danger')
            else:
                o = (d.execute('SELECT MAX(ordine) FROM puma_campi_sede WHERE comando_id=?', (sede,)).fetchone()[0] or 0) + 1
                d.execute('INSERT INTO puma_campi_sede(comando_id, etichetta, tipo, opzioni, obbligatorio, ordine) VALUES(?,?,?,?,?,?)',
                          (sede, et, tipo, f.get('opzioni', '').strip()[:2000] or None, 1 if f.get('obbligatorio') else 0, o))
                flash(f'Campo «{et}» aggiunto.', 'success')
        elif a == 'salva':
            for k in campi_di(d, sede, solo_attivi=False):
                i = k['id']
                if f.get(f'elimina_{i}'):
                    d.execute('DELETE FROM puma_campi_sede WHERE id=?', (i,)); continue
                et = f.get(f'etichetta_{i}', '').strip()[:80] or k['etichetta']
                d.execute('UPDATE puma_campi_sede SET etichetta=?, opzioni=?, obbligatorio=?, attivo=?, ordine=? WHERE id=?',
                          (et, f.get(f'opzioni_{i}', '').strip()[:2000] or None, 1 if f.get(f'obbligatorio_{i}') else 0,
                           1 if f.get(f'attivo_{i}') else 0, f.get(f'ordine_{i}', type=int) or 0, i))
            flash('Campi salvati.', 'success')
        d.commit(); return redirect(url_for('puma.campi_personalizzati', sede=sede))
    s = next(x for x in sedi if x['id'] == sede)
    n = d.execute('SELECT COUNT(*) FROM utenti WHERE comando_id=?', (sede,)).fetchone()[0]
    return render_template('puma/campi.html', sedi=sedi, s=s, campi=campi_di(d, sede, solo_attivi=False), tipi=TIPI, n_persone=n)
