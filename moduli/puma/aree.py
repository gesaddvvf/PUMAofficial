"""Pagine v1.3: Didattica e documentazione, Area personale, Livelli di accesso, Inviti, Aree corsi."""
import json, secrets
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, abort, g
import config
from . import bp, current_user, get_db, elenco
from . import ruoli as R
from .navigazione import GRUPPI


def _acc(): return R.accessi()


# ---------------- DIDATTICA E DOCUMENTAZIONE ----------------
IN_ARRIVO = [('🎬', 'Lezioni e presentazioni', 'Materiale delle lezioni dei corsi, per area.'),
             ('📹', 'Video didattici', 'Video delle manovre previste, collegati alle schede.'),
             ('✅', 'Quiz di autoverifica', 'Domande per area corsi, con esito nel libretto.'),
             ('🧰', 'Schede tecniche', 'Attrezzature e DPI: schede e controlli periodici.')]
BASE_DIDATTICA = 5   # schede di serie in GRUPPI['didattica']: le altre le aggiungono i moduli con navigazione.registra()


@bp.route('/didattica')
def didattica():
    current_user()
    extra = [dict(url=url_for(e, **a), etichetta=et) for e, a, et, p in GRUPPI['didattica']['schede'][BASE_DIDATTICA:]]
    n = {r['categoria']: r['n'] for r in get_db().execute('SELECT categoria, COUNT(*) n FROM puma_documenti GROUP BY categoria')}
    return render_template('puma/didattica.html', extra=extra, in_arrivo=IN_ARRIVO, n=n)


# ---------------- AREA PERSONALE ----------------
@bp.route('/personale')
def personale():
    from .libretto import libretto
    u = current_user(); d = get_db(); y = date.today().year
    lib = libretto(d, g.utente, y)
    nomi = {r['id']: r for r in d.execute('SELECT id, nome, sigla, settore FROM puma_livelli')}
    possesso = sorted(((nomi[k], v) for k, v in lib['possesso'].items() if k in nomi), key=lambda x: (x[0]['settore'] or '', x[0]['nome']))
    oggi = date.today().isoformat()
    aree_mie = {(t['settore'] or '').upper() for t, _ in possesso}
    prossimi = [e for e in elenco('puma_eventi', u, "data>=? AND stato!='chiuso'", (oggi,), order='data, ora_inizio')
                if (e['tipologia'] or '').upper() in aree_mie][:8]
    iscritto = {r[0] for r in d.execute('SELECT evento_id FROM puma_checkin WHERE username=?', (u['username'],))}
    wauc = d.execute('SELECT * FROM anagrafica_wauc WHERE utente_id=?', (g.utente['id'],)).fetchone()
    return render_template('puma/personale.html', lib=lib, possesso=possesso, prossimi=prossimi, iscritto=iscritto, wauc=wauc,
                           ruoli=_acc().righe, admin=_acc().admin, y=y, oggi=oggi)


@bp.route('/personale/attivita')
def mie_attivita():
    from .libretto import Catalogo, attivita
    current_user(); d = get_db()
    att = attivita(Catalogo(d), g.utente['email'])
    anni = sorted({a['anno'] for a in att} | {date.today().year}, reverse=True)
    y = request.args.get('anno', type=int) or anni[0]
    tipo = request.args.get('tipo', '')
    righe = [a for a in reversed(att) if a['anno'] == y and (not tipo or a['tipo'] == tipo)]
    return render_template('puma/mie_attivita.html', righe=righe, anni=anni, y=y, tipo=tipo,
                           ore=sum(a['ore'] or 0 for a in righe))


# ---------------- LIVELLI DI ACCESSO ----------------
def _sedi_gestibili(c, acc):
    sedi = acc.sedi('ruoli')
    q = """SELECT k.id, k.nome, k.tipo, cd.direzione_id FROM comandi k LEFT JOIN puma_comando_dir cd ON cd.comando_id=k.id
           ORDER BY CASE k.tipo WHEN 'comando' THEN 0 WHEN 'direzione' THEN 1 ELSE 2 END, k.nome"""
    return [r for r in c.execute(q) if sedi is None or r['id'] in sedi]


def _puo_gestire(acc, ruolo, sede_id):
    if not acc.puo('ruoli') or ruolo not in acc.assegnabili(): return False
    if acc.admin: return True
    sedi = acc.sedi('ruoli')
    return sede_id is not None and (sedi is None or sede_id in sedi)


def _livello_ruolo(c, ruolo):
    r = c.execute('SELECT livello FROM puma_ruoli WHERE codice=?', (ruolo,)).fetchone()
    return r['livello'] if r else None


@bp.route('/accessi', methods=['GET', 'POST'])
def accessi():
    u = current_user(); acc = _acc(); d = get_db()
    if not acc.puo('ruoli'): abort(403)
    sedi = _sedi_gestibili(d, acc); ids = {s['id'] for s in sedi}
    if request.method == 'POST':
        f = request.form; azione = f.get('azione')
        if azione == 'assegna':
            uid = f.get('utente_id', type=int); ruolo = f.get('ruolo', ''); liv = _livello_ruolo(d, ruolo)
            sede = None if liv in ('nazionale', 'base') else f.get('sede_id', type=int)
            area = f.get('settore') or '*'
            p = d.execute('SELECT * FROM utenti WHERE id=?', (uid,)).fetchone()
            sede_ok = sede is None or d.execute('SELECT tipo FROM comandi WHERE id=?', (sede,)).fetchone()
            if not p or not liv: flash('Scegli persona e livello.', 'danger')
            elif liv in ('direzione', 'comando') and not sede: flash('Scegli la sede del livello.', 'danger')
            elif liv == 'direzione' and sede_ok['tipo'] != 'direzione': flash('I livelli «Direzione» vanno su una Direzione Regionale.', 'danger')
            elif liv == 'comando' and sede_ok['tipo'] == 'direzione': flash('I livelli «Comando» vanno su un Comando (o CON/SOCAV), non su una Direzione.', 'danger')
            elif area != '*' and not d.execute('SELECT 1 FROM puma_settori WHERE codice=?', (area,)).fetchone(): flash('Area corsi non valida.', 'danger')
            elif not _puo_gestire(acc, ruolo, sede if sede is not None else p['comando_id']): abort(403)
            elif not acc.admin and p['comando_id'] not in ids: abort(403)
            else:
                R.assegna(d, uid, ruolo, sede, area, u['username'])
                if p['stato'] == 'in_attesa':
                    d.execute("UPDATE utenti SET stato='attivo', approvato_da=?, approvato_il=? WHERE id=?",
                              (g.utente['id'], datetime.now().isoformat(timespec='seconds'), uid))
                import db as portale_db
                portale_db.audit(d, u['username'], 'ruolo_assegnato', f"{p['email']} {ruolo} sede={sede} area={area}")
                d.commit(); flash('Livello di accesso assegnato.', 'success')
        elif azione == 'togli':
            a = d.execute('SELECT a.*, r.livello FROM puma_ruoli_utente a JOIN puma_ruoli r ON r.codice=a.ruolo WHERE a.id=?', (f.get('id', type=int),)).fetchone()
            if not a: abort(404)
            if a['utente_id'] == g.utente['id'] and a['ruolo'] in ('AMM_GEN', 'AMM_DIR', 'AMM_CMD'):
                flash('Non puoi togliere a te stesso un livello di amministratore: chiedilo a un altro amministratore.', 'danger')
            elif not _puo_gestire(acc, a['ruolo'], a['sede_id'] if a['sede_id'] is not None else -1) and not acc.admin: abort(403)
            else:
                R.togli(d, a['id'])
                import db as portale_db
                portale_db.audit(d, u['username'], 'ruolo_tolto', f"utente={a['utente_id']} {a['ruolo']} sede={a['sede_id']} area={a['settore']}")
                d.commit(); flash('Livello di accesso tolto.', 'success')
        elif azione == 'abilita':
            uid = f.get('utente_id', type=int)
            p = d.execute("SELECT * FROM utenti WHERE id=? AND stato='in_attesa'", (uid,)).fetchone()
            if not p or (not acc.admin and p['comando_id'] not in ids): abort(403)
            R.assegna(d, uid, 'OPERATORE', None, '*', u['username'])
            d.execute("UPDATE utenti SET stato='attivo', approvato_da=?, approvato_il=? WHERE id=?",
                      (g.utente['id'], datetime.now().isoformat(timespec='seconds'), uid))
            d.commit(); flash(f"{p['nome']} {p['cognome']} abilitato come Operatore.", 'success')
        return redirect(url_for('puma.accessi', **{k: v for k, v in request.args.items()}))
    filtro = request.args.get('sede', type=int)
    q = """SELECT u.*, k.nome AS comando FROM utenti u LEFT JOIN comandi k ON k.id=u.comando_id WHERE u.stato!='disabilitato'"""
    par = []
    if not acc.admin:
        if not ids: q += ' AND 0'
        else: q += ' AND u.comando_id IN (%s)' % ','.join('?' * len(ids)); par += list(ids)
    if filtro: q += ' AND u.comando_id=?'; par.append(filtro)
    sel = request.args.get('utente', type=int)
    if sel: q += ' AND u.id=?'; par.append(sel)
    persone = d.execute(q + " ORDER BY u.stato='in_attesa' DESC, u.cognome, u.nome", par).fetchall()
    ass = {}
    for r in d.execute("""SELECT a.*, r.nome AS ruolo_nome, r.livello, k.nome AS sede_nome, COALESCE(s.nome, 'tutte le aree') AS area_nome
            FROM puma_ruoli_utente a JOIN puma_ruoli r ON r.codice=a.ruolo LEFT JOIN comandi k ON k.id=a.sede_id
            LEFT JOIN puma_settori s ON s.codice=a.settore ORDER BY r.ordine"""):
        ass.setdefault(r['utente_id'], []).append(r)
    assegnabili = [r for r in R.ruoli(d) if r['codice'] in acc.assegnabili()]
    return render_template('puma/accessi.html', persone=persone, ass=ass, sedi=sedi, aree=R.aree(d), assegnabili=assegnabili,
                           tutti_ruoli=R.ruoli(d), matrice=R.MATRICE, capacita=R.CAPACITA, filtro=filtro, sel=sel,
                           gestibile=lambda a: acc.admin or _puo_gestire(acc, a['ruolo'], a['sede_id'] if a['sede_id'] is not None else -1),
                           tutti_comandi=[s for s in sedi if s['tipo'] != 'direzione'])


@bp.route('/livelli')
def livelli_utente():
    return redirect(url_for('puma.accessi'))


# ---------------- INVITI ----------------
def indirizzo_pubblico():
    """Indirizzo da mettere nei link: PUMA_INDIRIZZO_PUBBLICO in puma.env oppure quello con cui si sta usando PUMA."""
    import os
    base = os.environ.get('PUMA_INDIRIZZO_PUBBLICO') or request.host_url
    return base.rstrip('/')


def indirizzi_rete():
    """Indirizzi IP di questo PC nella rete (per AVVIA_RETE): servono ai colleghi per aprire PUMA."""
    import socket
    ip = set()
    try:
        for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET): ip.add(x[4][0])
    except OSError: pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); ip.add(s.getsockname()[0]); s.close()
    except OSError: pass
    return sorted(i for i in ip if not i.startswith('127.'))


@bp.route('/inviti', methods=['GET', 'POST'])
def inviti():
    from auth_imap import norm_email
    u = current_user(); acc = _acc(); d = get_db()
    if not acc.puo('ruoli'): abort(403)
    sedi = _sedi_gestibili(d, acc)
    if request.method == 'POST':
        f = request.form
        if f.get('azione') == 'annulla':
            d.execute('DELETE FROM puma_inviti WHERE token=? AND usato_il IS NULL AND (creato_da=? OR ?)', (f.get('token'), u['username'], int(acc.admin)))
            d.commit(); flash('Invito annullato.', 'success'); return redirect(url_for('puma.inviti'))
        email, err = norm_email(f.get('email', ''))
        ruolo = f.get('ruolo') or 'OPERATORE'; liv = _livello_ruolo(d, ruolo)
        cid = f.get('comando_id', type=int); sede = None if liv in ('nazionale', 'base') else f.get('sede_id', type=int)
        giorni = f.get('giorni', type=int) or 14
        if err: flash(f'Utente non valido: {err}', 'danger')
        elif not cid or not any(s['id'] == cid for s in sedi): flash('Scegli il Comando di appartenenza.', 'danger')
        elif liv in ('direzione', 'comando') and not sede: flash('Scegli la sede del livello.', 'danger')
        elif not _puo_gestire(acc, ruolo, sede if sede is not None else cid): abort(403)
        else:
            tok = secrets.token_urlsafe(18)
            d.execute("""INSERT INTO puma_inviti(token,email,comando_id,ruolo,sede_id,settore,creato_da,creato_il,scade_il) VALUES(?,?,?,?,?,?,?,?,?)""",
                      (tok, email, cid, ruolo, sede, f.get('settore') or '*', u['username'], datetime.now().isoformat(timespec='seconds'),
                       (date.today() + timedelta(days=min(max(giorni, 1), 90))).isoformat()))
            d.commit(); flash('Invito creato: copia il link e mandalo al collega.', 'success')
            return redirect(url_for('puma.inviti', nuovo=tok))
        return redirect(url_for('puma.inviti'))
    righe = d.execute("""SELECT i.*, k.nome AS comando, r.nome AS ruolo_nome, s.nome AS sede_nome FROM puma_inviti i
        LEFT JOIN comandi k ON k.id=i.comando_id LEFT JOIN puma_ruoli r ON r.codice=i.ruolo LEFT JOIN comandi s ON s.id=i.sede_id
        WHERE ? OR i.creato_da=? ORDER BY i.creato_il DESC LIMIT 200""", (int(acc.admin), u['username'])).fetchall()
    base = indirizzo_pubblico()
    locale = request.host.split(':')[0] in ('127.0.0.1', 'localhost')
    return render_template('puma/inviti.html', righe=righe, base=base, nuovo=request.args.get('nuovo'), sedi=sedi, aree=R.aree(d),
                           assegnabili=[r for r in R.ruoli(d) if r['codice'] in acc.assegnabili()], locale=locale,
                           ip=indirizzi_rete(), porta=config.PORT, in_rete=config.HOST not in ('127.0.0.1', 'localhost'),
                           mio_comando=u['comando_id'], oggi=date.today().isoformat())


# ---------------- AREE CORSI ----------------
@bp.route('/aree-corsi', methods=['GET', 'POST'])
def aree_corsi():
    import re
    current_user(); acc = _acc(); d = get_db()
    if not acc.puo('aree'): abort(403)
    if request.method == 'POST':
        f = request.form; a = f.get('azione')
        if a == 'nuova':
            cod = re.sub(r'[^A-Z0-9]', '', f.get('codice', '').upper())[:12]; nome = f.get('nome', '').strip()[:80]
            if not cod or not nome: flash('Indica sigla (lettere e numeri) e nome dell\'area.', 'danger')
            elif d.execute('SELECT 1 FROM puma_settori WHERE codice=?', (cod,)).fetchone(): flash(f'L\'area {cod} esiste già.', 'danger')
            else:
                o = (d.execute('SELECT MAX(ordine) FROM puma_settori').fetchone()[0] or 0) + 1
                d.execute('INSERT INTO puma_settori(codice, nome, descrizione, ordine, modificata) VALUES(?,?,?,?,1)', (cod, nome, f.get('descrizione', '').strip()[:300] or None, o))
                flash(f'Area {cod} creata.', 'success')
        elif a == 'salva':
            for r in d.execute('SELECT codice FROM puma_settori').fetchall():
                k = r['codice']
                nome = f.get('nome_' + k, '').strip()[:80]
                if not nome: continue
                d.execute('UPDATE puma_settori SET nome=?, descrizione=?, ordine=?, attiva=?, modificata=1 WHERE codice=?',
                          (nome, f.get('descr_' + k, '').strip()[:300] or None, f.get('ordine_' + k, type=int) or 0, 1 if f.get('attiva_' + k) else 0, k))
            flash('Aree corsi salvate.', 'success')
        elif a == 'corsi':
            aree = {r['codice'] for r in d.execute('SELECT codice FROM puma_settori')}
            for t in d.execute('SELECT id, settore FROM puma_livelli').fetchall():
                v = f.get(f"area_{t['id']}")
                if v and v in aree and v != t['settore']:
                    d.execute('UPDATE puma_livelli SET settore=?, area_manuale=1 WHERE id=?', (v, t['id']))
                d.execute('UPDATE puma_livelli SET attiva=? WHERE id=?', (1 if f.get(f"attivo_{t['id']}") else 0, t['id']))
            flash('Corsi aggiornati.', 'success')
        d.commit(); return redirect(url_for('puma.aree_corsi') + ('#corsi' if a == 'corsi' else ''))
    aree = d.execute("""SELECT s.*, (SELECT COUNT(*) FROM puma_livelli l WHERE l.settore=s.codice) n_corsi,
        (SELECT COUNT(*) FROM puma_ruoli_utente r WHERE r.settore=s.codice) n_ruoli FROM puma_settori s ORDER BY s.ordine, s.nome""").fetchall()
    corsi = d.execute('SELECT * FROM puma_livelli ORDER BY settore, ordine, nome').fetchall()
    return render_template('puma/aree_corsi.html', aree=aree, corsi=corsi)
