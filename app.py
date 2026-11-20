"""P.U.M.A. — Piattaforma Unificata Monitoraggio Addestramenti.   Avvio:  python app.py   (oppure AVVIA.bat / AVVIA_PROVA.bat)

Struttura: questo file è il «nucleo» (accesso con credenziali dipartimentali, profilo da WAUC, utenti e permessi,
amministrazione). Le applicazioni stanno in moduli/<nome>/: PUMA è il modulo principale e si apre subito dopo il login.
Per aggiungere in futuro un'altra applicazione basta copiare moduli/_esempio (vedi docs/SVILUPPO.md)."""
import config  # deve essere il primo import: aggiunge libs/ al percorso
import os, re, time, hmac, secrets, datetime, importlib, pkgutil, threading
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort
import config, db, profilo
from auth_imap import verifica, estrai_nome_cognome, norm_email, EMAIL_RE
import logging
config.avvia_log()
log_accesso = logging.getLogger('accesso')

LIVELLI = ['lettura', 'scrittura', 'gestore']
app = Flask(__name__)
app.secret_key = config.secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=8))
db.migra()



MODULI = {}
NAVIGAZIONE = None
from urllib.parse import urlparse as _up
_t = _up(os.environ.get('PUMA_TILE_URL', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'))
TILE_HOST = f'{_t.scheme}://{_t.netloc}'   # server delle mappe (P.U.M.A.): unica origine esterna ammessa per le immagini

def carica_moduli():
    """Ogni cartella in moduli/ con MODULO (dict) e bp (Blueprint) diventa un'applicazione, raggiungibile su /<codice>/
    (PUMA: /puma/). Le cartelle che iniziano con «_» (es. _esempio) sono modelli e non vengono caricate."""
    global NAVIGAZIONE
    for m in sorted(pkgutil.iter_modules([os.path.join(config.BASE_DIR, 'moduli')]), key=lambda x: (x.name != config.MODULO_PRINCIPALE, x.name)):
        if m.name.startswith('_'): continue
        mod = importlib.import_module(f'moduli.{m.name}')
        info = mod.MODULO
        MODULI[info['codice']] = info
        app.register_blueprint(mod.bp, url_prefix=f"/{info['codice']}")
        if m.name == config.MODULO_PRINCIPALE:   # intestazione e menu del sito (se il modulo principale li definisce)
            try: NAVIGAZIONE = importlib.import_module(f'moduli.{m.name}.navigazione')
            except ImportError: NAVIGAZIONE = None
        with db.connect() as c:
            c.execute('INSERT OR IGNORE INTO settori(codice,nome,descrizione) VALUES(?,?,?)',
                      (info['settore'], info.get('settore_nome', info['settore'].capitalize()), info.get('descrizione')))
carica_moduli()

if config.PROVA:   # utenti fittizi e dati di prova (db separato in data_prova/), ricreati se mancano
    import prova
    prova.prepara()

def data_iso(s):
    """'2024-05-31' -> '2024-05-31'; None se vuota o non valida."""
    try: return datetime.date.fromisoformat(s.strip()[:10]).isoformat() if s and s.strip() else None
    except ValueError: return None

@app.template_filter('datait')
def datait(s): return f'{s[8:10]}/{s[5:7]}/{s[:4]}' if s and len(s) >= 10 else ''

def liv_indice(l): return LIVELLI.index(l) if l in LIVELLI else -1
def puo(settore, minimo='lettura'):
    """Utilizzabile anche dentro i moduli: puo('lance','scrittura')."""
    if not g.get('utente'): return False
    if g.utente['is_admin']: return True
    return liv_indice(g.perm.get(settore)) >= liv_indice(minimo)

app.extensions['puo'] = puo   # per i moduli: current_app.extensions['puo']('settore', 'scrittura')

@app.context_processor
def ctx():
    if 'csrf' not in session: session['csrf'] = secrets.token_hex(16)
    u = g.get('utente')
    app_utente = [m for m in MODULI.values() if puo(m['settore'])] if u and u['stato'] == 'attivo' else []
    nav = NAVIGAZIONE.contesto(u if u and u['stato'] == 'attivo' else None, puo) if NAVIGAZIONE and request.endpoint else {}
    return dict(csrf=session['csrf'], utente=u, puo=puo, versione=config.VERSIONE, dev_auth=config.DEV_AUTH,
                prova=config.PROVA, nome_app=config.NOME_APP, nome_esteso=config.NOME_ESTESO, app_utente=app_utente, **nav)

@app.before_request
def prima():
    g.utente, g.perm = None, {}
    if request.endpoint is None or request.endpoint == 'static': return
    if request.method == 'POST':
        sess_tok = session.get('csrf', '')
        if not sess_tok or not hmac.compare_digest(sess_tok, request.form.get('csrf', '')): abort(400)
    uid = session.get('uid')
    if uid:
        with db.connect() as c:
            u = c.execute('SELECT u.*, k.nome AS comando FROM utenti u LEFT JOIN comandi k ON k.id=u.comando_id WHERE u.id=?', (uid,)).fetchone()
            if u and u['stato'] != 'disabilitato':
                g.utente = u
                g.perm = {r['codice']: r['livello'] for r in c.execute(
                    'SELECT s.codice, p.livello FROM permessi p JOIN settori s ON s.id=p.settore_id WHERE p.utente_id=?', (uid,))}
        if not g.utente: session.clear()
    if not g.utente:
        return None if request.endpoint in ('login', 'stato_rete') else redirect(url_for('login'))
    if not g.utente['profilo_confermato'] and request.endpoint not in ('profilo_view', 'profilo_spec_aggiungi', 'logout'):
        return redirect(url_for('profilo_view'))
    if g.utente['stato'] == 'in_attesa' and request.endpoint not in ('attesa', 'logout', 'profilo_view', 'profilo_spec_aggiungi'):
        return redirect(url_for('attesa'))
    if request.blueprint in MODULI and not puo(MODULI[request.blueprint]['settore']):
        abort(403)

@app.after_request
def intestazioni(r):
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['X-Frame-Options'] = 'DENY'
    r.headers['Referrer-Policy'] = 'same-origin'
    r.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: " + TILE_HOST + "; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
    r.headers['Cache-Control'] = 'no-store' if request.endpoint != 'static' else 'public, max-age=3600'
    return r

@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def errore(e):
    msg = {400: 'Richiesta non valida o sessione scaduta: ricarica la pagina.', 403: 'Non hai i permessi per questa sezione.', 404: 'Pagina non trovata.'}[e.code]
    return render_template('errore.html', codice=e.code, msg=msg), e.code

# ── Accesso ──────────────────────────────────────────────────────────────────
TENTATIVI = {}
def bloccato(k):
    t = time.time(); TENTATIVI[k] = [x for x in TENTATIVI.get(k, []) if t - x < 300]
    return len(TENTATIVI[k]) >= 5

def pagina_login():
    return render_template('login.html', utenti_prova=prova.UTENTI if config.PROVA else [])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.utente: return redirect(url_for('home'))
    if request.method == 'POST':
        email, err = norm_email(request.form.get('email', ''))   # aggiunge @vigilfuoco.it se manca
        if err:
            flash(f'Accesso negato: {err}', 'danger'); return pagina_login()
        chiave = f"{request.remote_addr}|{email}"
        if bloccato(chiave):
            flash('Troppi tentativi. Riprova tra qualche minuto.', 'danger')
            return pagina_login()
        ok, err, dettaglio = verifica(email, request.form.get('password', ''))
        if not ok:
            log_accesso.warning('Accesso NEGATO per %s: %s', email, dettaglio)
            with db.connect() as c: db.audit(c, email, 'accesso_negato', dettaglio)
            TENTATIVI.setdefault(chiave, []).append(time.time())
            flash(f'Accesso negato: {err}', 'danger')
            return pagina_login()
        log_accesso.info('Accesso riuscito per %s (%s)', email, dettaglio)
        now = datetime.datetime.now().isoformat(timespec='seconds')
        with db.connect() as c:
            u = c.execute('SELECT * FROM utenti WHERE email=?', (email,)).fetchone()
            if not u:
                n, cg = estrai_nome_cognome(email)
                cur = c.execute('INSERT INTO utenti(email,nome,cognome,creato_il) VALUES(?,?,?,?)', (email, n, cg, now))
                db.audit(c, email, 'primo_accesso', 'account creato, in attesa di abilitazione')
                u = c.execute('SELECT * FROM utenti WHERE id=?', (cur.lastrowid,)).fetchone()
            if u['stato'] == 'disabilitato':
                flash('Account disabilitato. Contatta un amministratore di P.U.M.A.', 'danger')
                return pagina_login()
            origine, errw = profilo.profila(c, u)   # ricerca con l'email inserita: WAUC, poi organico locale
            if origine and not u['profilo_confermato']: db.audit(c, email, 'profilo_precompilato', origine)
            if errw: db.audit(c, email, 'wauc_errore', errw[:200])
            elif origine != 'wauc' and config.WAUC_ATTIVO:
                db.audit(c, email, 'wauc_non_trovato', 'nessun errore di collegamento: la persona non compare nelle sedi interrogate (vedi PROVA_WAUC.bat)')
                log_accesso.warning('WAUC: %s non trovato nelle sedi interrogate', email)
            profilo.assicura_catalogo(c)   # elenchi completi di specializzazioni e qualifiche (al primo accesso e poi ogni 24 ore)
            c.execute('UPDATE utenti SET ultimo_accesso=? WHERE id=?', (now, u['id']))
        session.clear(); session.permanent = True
        session['uid'] = u['id']; session['csrf'] = secrets.token_hex(16)
        return redirect(url_for('home'))
    return pagina_login()

@app.route('/stato-rete')
def stato_rete():
    """Stato dei collegamenti alla rete VVF (posta dipartimentale per il login, WAUC per i dati): usato dalla pagina di accesso."""
    import rete
    return rete.stato_json()

@app.route('/logout', methods=['POST'])
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/profilo', methods=['GET', 'POST'])
def profilo_view():
    """Dati reperiti da WAUC/organico: l'utente li conferma. Dove esiste un elenco di valori trovati in WAUC si può scegliere solo tra quelli."""
    u = g.utente
    with db.connect() as c:
        if request.method == 'GET': profilo.assicura_catalogo(c)
        quals = c.execute("SELECT * FROM qualifiche_wauc WHERE ambito='VVF' OR (codice=? AND cod_gruppo=?) ORDER BY desc_gruppo, descrizione", (u['cod_qualifica'] or '', u['cod_gruppo'] or '')).fetchall()
        tipi = c.execute("SELECT codice, descrizione FROM valori_wauc WHERE campo='tipo_personale' ORDER BY descrizione").fetchall()
        turni = [r[0] for r in c.execute("SELECT codice FROM valori_wauc WHERE campo='turno' ORDER BY codice")]
        salti = [r[0] for r in c.execute("SELECT codice FROM valori_wauc WHERE campo='salto_turno' ORDER BY CAST(codice AS INTEGER), codice")]
        if request.method == 'POST':
            f = request.form; err = None
            blocca_nome = u['origine_profilo'] == 'wauc'            # nome e cognome arrivati da WAUC non si modificano
            v = {k: f.get(k, '').strip()[:80] for k in ('matricola', 'telefono')}
            v['nome'] = u['nome'] if blocca_nome else f.get('nome', '').strip()[:80]
            v['cognome'] = u['cognome'] if blocca_nome else f.get('cognome', '').strip()[:80]
            cid = f.get('comando_id', type=int)
            com = c.execute('SELECT * FROM comandi WHERE id=?', (cid,)).fetchone()
            if not v['nome'] or not v['cognome']: err = 'Nome e cognome sono obbligatori.'
            elif not com: err = 'Seleziona il comando (provincia) di appartenenza.'
            # qualifica ("codice|gruppo" dall'elenco WAUC)
            qv = f.get('qualifica', '').strip(); qual = (None, None, None)
            if not err and quals:
                if qv:
                    cod, _, grp = qv.partition('|'); r = next((x for x in quals if x['codice'] == cod and x['cod_gruppo'] == grp), None)
                    if r: qual = (r['descrizione'], cod, grp)
                    else: err = 'Qualifica non valida: scegli un valore dell\'elenco.'
            elif not err: qual = (qv[:80] or None, None, None)
            # distaccamento: solo valori trovati per quel comando
            dv = f.get('distaccamento', '').strip()[:80]
            if not err:
                dcat = [r[0] for r in c.execute('SELECT descrizione FROM distaccamenti_wauc WHERE cod_sede=?', (com['sigla'] or '',))]
                if dcat and dv and dv not in dcat and dv != (u['distaccamento'] or ''): err = 'Distaccamento non valido per il comando scelto.'
            # tipo personale, turno, salto turno
            tv = f.get('tipo_personale', '').strip(); tipo = (None, None)
            if not err and tipi:
                if tv:
                    r = next((x for x in tipi if x['codice'] == tv), None)
                    if r: tipo = (tv, r['descrizione'])
                    else: err = 'Tipo di personale non valido.'
            elif not err: tipo = (None, tv[:80] or None)
            tur, sal = f.get('turno', '').strip(), f.get('salto_turno', '').strip()
            if not err and ((turni and tur and tur not in turni) or (salti and sal and sal not in salti)): err = 'Turno o salto turno non validi: scegli un valore dell\'elenco.'
            if err:
                flash(err, 'danger'); return redirect(url_for('profilo_view'))
            v['qualifica'], v['distaccamento'] = qual[0], dv
            nuovo = dict(**v, comando_id=cid, cod_qualifica=qual[1], cod_gruppo=qual[2], cod_tipo_personale=tipo[0], tipo_personale=tipo[1], turno=tur or None, salto_turno=sal or None)
            invariato = all((u[k] or None) == (nuovo[k] or None) for k in ('qualifica', 'distaccamento', 'comando_id', 'turno', 'salto_turno', 'cod_tipo_personale', 'nome', 'cognome'))
            orig = u['origine_profilo'] if u['origine_profilo'] in ('wauc', 'organico') and invariato else 'manuale'
            c.execute('UPDATE utenti SET ' + ','.join(f'{k}=?' for k in nuovo) + ',origine_profilo=?,profilo_confermato=1 WHERE id=?', (*nuovo.values(), orig, u['id']))
            # specializzazioni: quelle di WAUC sono bloccate; l'utente può spuntare altre dell'elenco WAUC
            wcod = {r[0] for r in c.execute("SELECT codice FROM specializzazioni_utente WHERE utente_id=? AND origine='wauc'", (u['id'],))}
            c.execute("DELETE FROM specializzazioni_utente WHERE utente_id=? AND origine='manuale'", (u['id'],))
            spunte = set(f.getlist('spec'))
            for r in c.execute('SELECT codice, descrizione FROM specializzazioni').fetchall():
                if r['codice'] in spunte and r['codice'] not in wcod:
                    c.execute("INSERT INTO specializzazioni_utente(utente_id,codice,descrizione,origine,inizio) VALUES(?,?,?, 'manuale', ?)", (u['id'], r['codice'], r['descrizione'], data_iso(f.get('data_' + r['codice'], ''))))
            profilo.salva_in_organico(c, u['email'], v, com['nome'])
            db.audit(c, u['email'], 'profilo_confermato', f'origine={orig}')
            return redirect(url_for('attesa' if u['stato'] == 'in_attesa' else 'home'))
        comandi = c.execute('SELECT * FROM comandi ORDER BY nome').fetchall()
        dist = c.execute('SELECT * FROM distaccamenti_wauc ORDER BY cod_sede, descrizione').fetchall()
        specs = c.execute("""SELECT s.codice, s.descrizione, s.fonte, su.origine, su.inizio, su.fine, (su.codice IS NOT NULL) AS posseduta,
            (su.codice IS NOT NULL AND (su.fine IS NULL OR su.fine='' OR su.fine>=date('now','localtime'))) AS valida
            FROM specializzazioni s LEFT JOIN specializzazioni_utente su ON su.codice=s.codice AND su.utente_id=?
            WHERE s.aggiornata_il IS NOT NULL
            ORDER BY valida DESC, posseduta DESC, s.codice""", (u['id'],)).fetchall()
    return render_template('profilo.html', comandi=comandi, specs=specs, quals=quals, tipi=tipi, turni=turni, salti=salti, dist=dist,
                           blocca_nome=u['origine_profilo'] == 'wauc')

@app.route('/profilo/specializzazione', methods=['POST'])
def profilo_spec_aggiungi():
    """Aggiunge una specializzazione non presente nell'elenco WAUC (codice e descrizione obbligatori, data facoltativa)."""
    f = request.form; cod = re.sub(r'\s+', '', f.get('codice', '')).upper()[:20]; desc = f.get('descrizione', '').strip()[:120]
    data = data_iso(f.get('data', ''))
    if not re.fullmatch(r'[A-Z0-9._/-]{1,20}', cod) or not desc:
        flash('Indica codice (lettere, numeri, . _ / -) e descrizione della specializzazione.', 'danger')
    elif f.get('data', '').strip() and not data:
        flash('Data non valida.', 'danger')
    else:
        with db.connect() as c:
            esito = profilo.aggiungi_specializzazione(c, g.utente['id'], cod, desc, data)
            if esito == 'nuova': db.audit(c, g.utente['email'], 'specializzazione_aggiunta', cod)
        flash({'nuova': f'Specializzazione {cod} aggiunta e spuntata: ricordati di confermare il profilo.', 'esistente': f'{cod} era già in elenco: l\'ho spuntata.',
               'gia_tua': f'{cod} risulta già tra le tue specializzazioni in WAUC.'}[esito], 'success')
    return redirect(url_for('profilo_view') + '#specializzazioni')

@app.route('/attesa')
def attesa():
    if g.utente['stato'] != 'in_attesa': return redirect(url_for('home'))
    return render_template('attesa.html')

@app.route('/')
def home():
    """Accesso diretto: si apre il modulo principale (PUMA). Se l'utente non vi è abilitato vede le altre applicazioni disponibili."""
    disponibili = [m for m in MODULI.values() if puo(m['settore'])]
    if any(m['codice'] == config.MODULO_PRINCIPALE for m in disponibili):
        return redirect(url_for(config.MODULO_PRINCIPALE + '.index'))
    return render_template('home.html', moduli=disponibili)

@app.route('/app')
def elenco_app():
    return render_template('home.html', moduli=[m for m in MODULI.values() if puo(m['settore'])])

# ── Amministrazione ──────────────────────────────────────────────────────────
def admin_only():
    if not g.utente['is_admin']: abort(403)

@app.route('/admin/utenti')
def admin_utenti():
    admin_only(); stato = request.args.get('stato', ''); cmd = request.args.get('comando', type=int)
    with db.connect() as c:
        q = 'SELECT u.*, k.nome AS comando FROM utenti u LEFT JOIN comandi k ON k.id=u.comando_id WHERE 1=1'
        par = []
        if stato: q += ' AND u.stato=?'; par.append(stato)
        if cmd: q += ' AND u.comando_id=?'; par.append(cmd)
        righe = c.execute(q + " ORDER BY u.stato='in_attesa' DESC, u.cognome", par).fetchall()
        comandi = c.execute('SELECT k.* FROM comandi k WHERE EXISTS(SELECT 1 FROM utenti u WHERE u.comando_id=k.id) ORDER BY k.nome').fetchall()
    return render_template('admin_utenti.html', righe=righe, filtro=stato, comandi=comandi, cmd=cmd)

@app.route('/admin/utenti/<int:uid>', methods=['GET', 'POST'])
def admin_utente(uid):
    admin_only()
    with db.connect() as c:
        u = c.execute('SELECT * FROM utenti WHERE id=?', (uid,)).fetchone() or abort(404)
        settori = c.execute('SELECT * FROM settori ORDER BY nome').fetchall()
        specs_u = c.execute("""SELECT su.codice, COALESCE(NULLIF(su.descrizione,''), s.descrizione, '') AS descrizione, su.origine, su.fine
            FROM specializzazioni_utente su LEFT JOIN specializzazioni s ON s.codice=su.codice WHERE su.utente_id=? ORDER BY su.codice""", (uid,)).fetchall()
        wauc_u = c.execute('SELECT * FROM anagrafica_wauc WHERE utente_id=?', (uid,)).fetchone()
        if request.method == 'POST':
            if uid == g.utente['id']:
                flash('Non puoi modificare il tuo stesso account: chiedi a un altro amministratore.', 'danger')
                return redirect(url_for('admin_utente', uid=uid))
            stato = request.form.get('stato')
            if stato not in ('in_attesa', 'attivo', 'disabilitato'): abort(400)
            cid = request.form.get('comando_id', type=int)
            adm = 1 if request.form.get('is_admin') else 0
            if u['stato'] != 'attivo' and stato == 'attivo':
                c.execute('UPDATE utenti SET approvato_da=?, approvato_il=? WHERE id=?',
                          (g.utente['id'], datetime.datetime.now().isoformat(timespec='seconds'), uid))
            c.execute('UPDATE utenti SET stato=?, comando_id=?, is_admin=? WHERE id=?', (stato, cid, adm, uid))
            c.execute('DELETE FROM permessi WHERE utente_id=?', (uid,))
            for s in settori:
                l = request.form.get(f"liv_{s['id']}")
                if l in LIVELLI: c.execute('INSERT INTO permessi VALUES(?,?,?)', (uid, s['id'], l))
            db.audit(c, g.utente['email'], 'modifica_utente', f"{u['email']} stato={stato} admin={adm}")
            flash('Utente aggiornato.', 'success')
            return redirect(url_for('admin_utenti'))
        comandi = c.execute('SELECT * FROM comandi ORDER BY nome').fetchall()
        perm = {r['settore_id']: r['livello'] for r in c.execute('SELECT * FROM permessi WHERE utente_id=?', (uid,))}
    return render_template('admin_utente.html', u=u, settori=settori, comandi=comandi, perm=perm, livelli=LIVELLI, specs=specs_u, wauc=wauc_u)

AZIONI_ANAGRAFICHE = {
    'sync_sedi': ('sedi', profilo.sincronizza_sedi, lambda r: f"{r['sedi']} sedi lette da WAUC ({r['comandi']} comandi, {r['collegati']} collegati ai Comandi del portale, {r['con_coordinate']} con coordinate)."),
    'sync_qualifiche': ('qualifiche', profilo.sincronizza_qualifiche, lambda n: f'{n} qualifiche lette da WAUC.'),
    'sync_specializzazioni': ('specializzazioni', profilo.sincronizza_specializzazioni, lambda n: f'{n} specializzazioni lette da WAUC.'),
}

@app.route('/admin/config', methods=['GET', 'POST'])
def admin_config():
    admin_only()
    with db.connect() as c:
        if request.method == 'POST':
            f = request.form
            if f.get('azione') in AZIONI_ANAGRAFICHE:   # «Crea o aggiorna dati» di sedi / qualifiche / specializzazioni
                voce, fn, esito = AZIONI_ANAGRAFICHE[f['azione']]
                try:
                    r = fn(c); db.audit(c, g.utente['email'], 'wauc_aggiorna_' + voce, str(r)[:200]); flash(esito(r), 'success')
                except Exception as e:
                    db.audit(c, g.utente['email'], 'wauc_errore', f'{voce}: {e}'[:200]); flash(f'{voce.capitalize()} non aggiornate: {str(e)[:160] or e.__class__.__name__}', 'danger')
                return redirect(url_for('admin_config'))
            if f.get('azione') == 'spec_sync':   # compatibilità: specializzazioni + qualifiche insieme
                try: ns, nq = profilo.sincronizza_catalogo(c); flash(f'{ns} specializzazioni e {nq} qualifiche lette da WAUC.', 'success')
                except Exception as e: flash(f'WAUC non raggiungibile: {e.__class__.__name__}', 'danger')
                return redirect(url_for('admin_config'))
            if f.get('azione') == 'scopri_sedi':
                ris = profilo.scopri_sedi(c); ok = {s: n for s, n in ris.items() if n}
                flash(f'{len(ok)} sedi con personale ({sum(ok.values())} persone); {sum(1 for n in ris.values() if n is None)} non raggiungibili.', 'success')
                return redirect(url_for('admin_config'))
            try:
                if f.get('azione') == 'comando' and f.get('nome', '').strip():
                    c.execute('INSERT INTO comandi(nome) VALUES(?)', (f['nome'].strip(),))
                    db.audit(c, g.utente['email'], 'nuovo_comando', f['nome'].strip())
                elif f.get('azione') == 'settore' and f.get('codice', '').strip() and f.get('nome', '').strip():
                    c.execute('INSERT INTO settori(codice,nome) VALUES(?,?)', (f['codice'].strip().lower(), f['nome'].strip()))
                    db.audit(c, g.utente['email'], 'nuovo_settore', f['codice'].strip().lower())
            except Exception:
                flash('Voce già esistente.', 'danger')
            return redirect(url_for('admin_config'))
        return render_template('admin_config.html', comandi=c.execute('SELECT * FROM comandi ORDER BY nome').fetchall(),
                               settori=c.execute('SELECT * FROM settori ORDER BY nome').fetchall(),
                               specs=c.execute("""SELECT s.codice, s.descrizione, s.fonte, s.data_inizio_validita, s.data_fine_validita,
                                   (SELECT COUNT(*) FROM specializzazioni_utente s2 WHERE s2.codice=s.codice AND (s2.fine IS NULL OR s2.fine='' OR s2.fine>=date('now','localtime'))) AS persone
                                   FROM specializzazioni s WHERE s.aggiornata_il IS NOT NULL ORDER BY s.codice""").fetchall(),
                               sedi=c.execute('SELECT * FROM wauc_sedi WHERE n_persone>0 ORDER BY codice').fetchall(), anag=profilo.stato_anagrafiche(c))

# ── Scheda dei comandi (contatti, PEC, NUE, siti) ───────────────────────────
EMAIL_SEMPLICE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
def _url(v):
    """'intranet.xx.it' -> 'http://intranet.xx.it'; solo http/https, senza spazi. None se vuoto; False se non valido."""
    v = (v or '').strip()
    if not v: return None
    if not re.match(r'^[a-z][a-z0-9+.-]*://', v, re.I): v = 'http://' + v
    return v[:300] if re.match(r'^https?://[^\s<>"\']+$', v, re.I) else False

def _num(v, lo, hi):
    v = (v or '').strip().replace(',', '.')
    if not v: return None
    try: x = float(v)
    except ValueError: return False
    return round(x, 6) if lo <= x <= hi else False

@app.route('/admin/comandi', methods=['GET', 'POST'])
def admin_comandi():
    """Scheda di ogni comando: telefoni, email, PEC, indirizzo, coordinate, NUE sì/no, sito e intranet. Dati inseriti a mano: gli aggiornamenti WAUC non li toccano."""
    admin_only(); q = request.args.get('q', '').strip(); mod = request.args.get('modifica', type=int)
    with db.connect() as c:
        if request.method == 'POST':
            f = request.form; cid = f.get('id', type=int); k = c.execute('SELECT * FROM comandi WHERE id=?', (cid,)).fetchone() or abort(404)
            t = lambda n, m=120: f.get(n, '').strip()[:m] or None
            v = dict(telefono=t('telefono', 40), telefono2=t('telefono2', 40), indirizzo=t('indirizzo', 160), cap=t('cap', 10), comune=t('comune', 80), nue_note=t('nue_note', 200), note=t('note', 400))
            err = None
            for campo in ('email', 'pec'):
                x = f.get(campo, '').strip().lower()[:120]
                if x and not EMAIL_SEMPLICE.match(x): err = f'{campo.upper() if campo == "pec" else "Email"} non valida.'
                v[campo] = x or None
            for campo in ('sito_web', 'sito_intranet'):
                u = _url(f.get(campo)); v[campo] = u or None
                if u is False: err = f'Indirizzo non valido ({campo.replace("_", " ")}): atteso http(s)://…'
            lat, lon = _num(f.get('lat'), -90, 90), _num(f.get('lon'), -180, 180)
            if lat is False or lon is False or (lat is None) != (lon is None): err = 'Coordinate non valide: indica latitudine e longitudine (es. 46.1405 e 12.2167), oppure lascia vuoto.'
            v['lat'], v['lon'] = (lat or None) if lat is not False else None, (lon or None) if lon is not False else None
            v['nue'] = {'si': 1, 'no': 0}.get(f.get('nue', ''))
            if err: flash(err, 'danger'); return redirect(url_for('admin_comandi', modifica=cid))
            c.execute('UPDATE comandi SET ' + ','.join(f'{a}=?' for a in v) + ',contatti_aggiornati_il=? WHERE id=?', (*v.values(), datetime.datetime.now().isoformat(timespec='seconds'), cid))
            db.audit(c, g.utente['email'], 'comando_scheda', k['nome']); flash(f"Scheda di {k['nome']} salvata.", 'success')
            return redirect(url_for('admin_comandi'))
        righe = c.execute("""SELECT k.*, s.descrizione AS sede_desc, s.lat AS wlat, s.lon AS wlon, s.coordinate_raw
                             FROM comandi k LEFT JOIN sedi_wauc s ON s.id=k.wauc_sede_id
                             WHERE ?='' OR k.nome LIKE ? OR k.sigla LIKE ? ORDER BY k.nome""", (q, f'%{q}%', f'%{q}%')).fetchall()
        m = next((r for r in righe if r['id'] == mod), None) if mod else None
        if mod and not m: m = c.execute('SELECT k.*, s.descrizione AS sede_desc, s.lat AS wlat, s.lon AS wlon, s.coordinate_raw FROM comandi k LEFT JOIN sedi_wauc s ON s.id=k.wauc_sede_id WHERE k.id=?', (mod,)).fetchone()
    return render_template('admin_comandi.html', righe=righe, m=m, q=q)

@app.route('/admin/organico', methods=['GET', 'POST'])
def admin_organico():
    admin_only(); mod = request.args.get('modifica', type=int); q = request.args.get('q', '').strip()
    with db.connect() as c:
        if request.method == 'POST':
            f = request.form; azione = f.get('azione')
            if azione == 'elimina':
                c.execute('DELETE FROM organico WHERE id=?', (f.get('id', type=int),)); db.audit(c, g.utente['email'], 'organico_elimina', f.get('id', ''))
            else:
                email, _e = norm_email(f.get('email', ''))
                if not email:
                    flash('Email non valida (atteso nome.cognome@vigilfuoco.it).', 'danger'); return redirect(url_for('admin_organico', modifica=f.get('id', type=int)))
                v = {k: f.get(k, '').strip()[:80] or None for k in ('nome', 'cognome', 'matricola', 'qualifica', 'comando', 'distaccamento', 'telefono')}
                if f.get('id', type=int): c.execute('UPDATE organico SET email=?,nome=?,cognome=?,matricola=?,qualifica=?,comando=?,distaccamento=?,telefono=? WHERE id=?', (email, *v.values(), f.get('id', type=int)))
                else:
                    try: c.execute('INSERT INTO organico(email,nome,cognome,matricola,qualifica,comando,distaccamento,telefono,importato_il) VALUES(?,?,?,?,?,?,?,?,?)', (email, *v.values(), datetime.datetime.now().isoformat(timespec='seconds')))
                    except Exception: flash('Email già presente in organico.', 'danger'); return redirect(url_for('admin_organico'))
                profilo.comando_id(c, v['comando']); db.audit(c, g.utente['email'], 'organico_salva', email)
                flash('Organico aggiornato.', 'success')
            return redirect(url_for('admin_organico'))
        righe = c.execute("SELECT * FROM organico WHERE ?='' OR email LIKE ? OR cognome LIKE ? OR nome LIKE ? ORDER BY cognome,nome LIMIT 500", (q, *[f'%{q}%']*3)).fetchall()
        m = c.execute('SELECT * FROM organico WHERE id=?', (mod,)).fetchone() if mod else None
        comandi = c.execute('SELECT * FROM comandi ORDER BY nome').fetchall()
    return render_template('admin_organico.html', righe=righe, m=m, comandi=comandi, q=q)

@app.route('/admin/audit')
def admin_audit():
    admin_only()
    with db.connect() as c:
        return render_template('admin_audit.html', righe=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 300').fetchall())

if __name__ == '__main__':
    from waitress import serve
    indirizzo = f"http://{'localhost' if config.HOST in ('127.0.0.1', '0.0.0.0') else config.HOST}:{config.PORT}"
    print('=' * 64)
    print(f' {config.NOME_APP} {config.VERSIONE} - {config.NOME_ESTESO}')
    if config.PROVA:
        print(' MODALITA PROVA: utenti fittizi, password "dev", nessuna VPN necessaria.')
        print(f' Dati di prova in: {config.DATA_DIR}')
    else:
        print(' MODALITA REALE: credenziali dipartimentali + dati WAUC (serve FortiClient VPN o rete VVF).')
        if config.DEV_AUTH: print(' *** ATTENZIONE: PUMA_DEV_AUTH attivo, password "dev" per tutti. Solo sviluppo! ***')
    print(f' Apri il browser su:  {indirizzo}')
    if config.HOST == '0.0.0.0': print(f' (raggiungibile anche dagli altri PC della rete sulla porta {config.PORT})')
    print(' Per fermare PUMA chiudi questa finestra o premi CTRL+C.')
    print('=' * 64)
    if config.env('APRI_BROWSER') == '1':
        import webbrowser
        threading.Timer(1.5, webbrowser.open, [indirizzo]).start()
    serve(app, host=config.HOST, port=config.PORT, threads=8)
