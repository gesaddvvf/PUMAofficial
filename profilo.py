"""Ricerca dell'utente (WAUC -> organico -> solo email), compilazione automatica del profilo, specializzazioni."""
import datetime, logging, re
import config, wauc
CAMPI = ('nome', 'cognome', 'matricola', 'qualifica', 'distaccamento', 'telefono')
VALIDA = "(s.fine IS NULL OR s.fine='' OR s.fine>=date('now','localtime'))"   # specializzazione non scaduta (alias tabella: s)
log = logging.getLogger('profilo')
ADESSO = lambda: datetime.datetime.now().isoformat(timespec='seconds')

def cerca_organico(c, email):
    return c.execute('SELECT * FROM organico WHERE lower(email)=?', (email.strip().lower(),)).fetchone()

def _parole(s):
    """minuscolo senza accenti né punteggiatura, parole separate da uno spazio: "Comando VV.F. L'AQUILA" -> 'comando vv f l aquila'."""
    import unicodedata
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()).split())

def trova_comando(c, valore):
    """Id del comando (= provincia) riconosciuto in `valore`: nome, MAIUSCOLO, sigla ('BL') o diciture tipo 'Comando VV.F. BELLUNO'. None se non è una provincia nota."""
    valore = (valore or '').strip()
    if not valore: return None
    righe = c.execute('SELECT id, nome, sigla FROM comandi').fetchall(); t = _parole(valore)
    for r in righe:
        if _parole(r['nome']) == t or (r['sigla'] and r['sigla'].lower() == valore.lower()): return r['id']
    cont = [r for r in righe if f" {_parole(r['nome'])} " in f' {t} ' and len(_parole(r['nome'])) > 3]
    return max(cont, key=lambda r: len(_parole(r['nome'])))['id'] if cont else None

def comando_id(c, valore):
    """Come trova_comando, ma se non è una provincia nota crea un nuovo comando con il valore ricevuto."""
    valore = (valore or '').strip()
    if not valore: return None
    return trova_comando(c, valore) or c.execute('INSERT INTO comandi(nome) VALUES(?)', (valore,)).lastrowid

def risolvi_sede(c, d):
    """(comando_id, distaccamento) dai dati: il comando viene dalla sigla/sede padre; se la sede è essa stessa un comando non c'è distaccamento."""
    cid = next((k for k in (trova_comando(c, t) for t in d.get('comando_testi', [])) if k), None)
    sede = (d.get('sede') or '').strip()
    if sede and _parole(sede).startswith('comando') and trova_comando(c, sede): return cid or trova_comando(c, sede), ''
    return cid, sede

def sedi_wauc(c):
    """Sedi (codici) in cui cercare: quelle impostate in config, altrimenti quelle scoperte con personale, altrimenti tutte le sigle provinciali."""
    if config.WAUC_SEDI: return list(config.WAUC_SEDI)
    note = [r[0] for r in c.execute('SELECT codice FROM wauc_sedi WHERE n_persone>0 ORDER BY n_persone DESC')]
    return note or [r[0] for r in c.execute('SELECT sigla FROM comandi WHERE sigla IS NOT NULL ORDER BY sigla')]

def registra_osservati(c):
    """Travasa nel db i valori incontrati nei record WAUC scaricati (qualifiche, tipi personale, turni, salti turno, distaccamenti)."""
    o = wauc.svuota_osservati()
    for cod, desc in o['tipo_personale'].items():
        c.execute('INSERT INTO valori_wauc VALUES(?,?,?) ON CONFLICT(campo,codice) DO UPDATE SET descrizione=excluded.descrizione', ('tipo_personale', cod, desc))
    for campo in ('turno', 'salto_turno'):
        for cod in o[campo]: c.execute('INSERT OR IGNORE INTO valori_wauc VALUES(?,?,NULL)', (campo, cod))
    for (cod, grp), v in o['qualifiche'].items(): c.execute('INSERT OR IGNORE INTO qualifiche_wauc VALUES(?,?,?,?,?,?,?)', (cod, grp, *v))
    for (sede, dist), desc in o['distaccamenti'].items():
        c.execute('INSERT INTO distaccamenti_wauc VALUES(?,?,?) ON CONFLICT(cod_sede,cod_distaccamento) DO UPDATE SET descrizione=excluded.descrizione', (sede, dist, desc))

def trova(c, email):
    """(origine, dati, specs, errore): origine = 'wauc' | 'organico' | None."""
    err = None
    if config.WAUC_ATTIVO:
        try:
            prima = c.execute('SELECT a.cod_sede FROM anagrafica_wauc a JOIN utenti u ON u.id=a.utente_id WHERE u.email=?', (email,)).fetchone()
            w = wauc.cerca_persona(email, sedi_wauc(c), prima[0] if prima and prima[0] else None)
            registra_osservati(c)
            if w: return 'wauc', w['dati'], w['specs'], None
        except Exception as e:
            err = str(e); log.warning('WAUC: %s', err)
            try: registra_osservati(c)
            except Exception: pass
    o = cerca_organico(c, email)
    if o: return 'organico', {**{k: o[k] for k in CAMPI if k != 'distaccamento'}, 'sede': o['distaccamento'], 'comando_testi': [o['comando']] if o['comando'] else []}, [], err
    return None, {}, [], err

def scopri_sedi(c):
    """Interroga tutte le sigle provinciali, memorizza le sedi con personale e i valori trovati. Ritorna {sede: n persone | None}."""
    ris = wauc.scopri_sedi([r[0] for r in c.execute('SELECT sigla FROM comandi WHERE sigla IS NOT NULL ORDER BY sigla')])
    for s, n in ris.items():
        if n is not None: c.execute('INSERT INTO wauc_sedi VALUES(?,?,?) ON CONFLICT(codice) DO UPDATE SET n_persone=excluded.n_persone, verificata_il=excluded.verificata_il', (s, n, ADESSO()))
    registra_osservati(c); return ris

def registra_specializzazioni(c, coppie):
    """Aggiunge/aggiorna il catalogo delle specializzazioni (codice -> descrizione)."""
    for cod, desc in coppie:
        c.execute("INSERT INTO specializzazioni(codice,descrizione,aggiornata_il) VALUES(?,?,?) ON CONFLICT(codice) DO UPDATE SET "
                  "descrizione=COALESCE(NULLIF(excluded.descrizione,''), descrizione), aggiornata_il=excluded.aggiornata_il, fonte='wauc'", (cod, desc or None, ADESSO()))

def _segna_sync(c, chiave):
    c.execute('INSERT INTO wauc_sync VALUES(?,?) ON CONFLICT(chiave) DO UPDATE SET eseguita_il=excluded.eseguita_il', (chiave, ADESSO()))

def sincronizza_specializzazioni(c):
    """Catalogo completo di /api/Specializzazioni (codice, descrizione, validità). Aggiunge/aggiorna, non cancella: restano quelle aggiunte dagli utenti.
    Ritorna il numero di voci; solleva eccezione se WAUC non risponde o non restituisce nulla (il db non viene toccato)."""
    voci = wauc.catalogo_specializzazioni_completo()
    if not voci: raise RuntimeError('WAUC non ha restituito nessuna specializzazione: nulla è stato modificato.')
    registra_specializzazioni(c, [(v[0], v[1]) for v in voci])
    for cod, _d, ini, fin in voci:
        c.execute('UPDATE specializzazioni SET data_inizio_validita=?, data_fine_validita=? WHERE codice=?', (ini or None, fin or None, cod))
    _segna_sync(c, 'specializzazioni'); return len(voci)

def sincronizza_qualifiche(c):
    """Catalogo completo di /api/ElencoQualifiche (CNVVF e Amministrazione Civile). Ritorna il numero di voci."""
    ql = wauc.catalogo_qualifiche()
    if not ql: raise RuntimeError('WAUC non ha restituito nessuna qualifica: nulla è stato modificato.')
    for q in ql:
        c.execute('INSERT INTO qualifiche_wauc VALUES(?,?,?,?,?,?,?) ON CONFLICT(codice,cod_gruppo) DO UPDATE SET descrizione=excluded.descrizione,nome=excluded.nome,'
                  'cod_settore=excluded.cod_settore,desc_gruppo=excluded.desc_gruppo,ambito=excluded.ambito', q)
    _segna_sync(c, 'qualifiche'); return len(ql)

def sincronizza_sedi(c, tipi=('CMD', 'UFC')):
    """Sedi da /api/Sedi (comandi CMD, uffici UFC...) nella tabella sedi_wauc e collegamento ai Comandi di PUMA (per sigla/nome provincia).
    La scheda di contatto dei comandi (telefono, PEC, NUE, siti...) non viene toccata. Ritorna dict(sedi, comandi, collegati, con_coordinate)."""
    voci = wauc.catalogo_sedi(tipi)
    if not voci: raise RuntimeError('WAUC non ha restituito nessuna sede: nulla è stato modificato.')
    n = conn = coord = 0; esatte = set()
    for tipo, rec in voci:
        d = wauc.estrai_sede(tipo, rec)
        if not d['id']: continue
        cid = trova_comando(c, d['codice']) or trova_comando(c, d['provincia']) or (trova_comando(c, d['descrizione']) if tipo == 'CMD' else None)
        d['comando_id'], d['aggiornata_il'] = cid, ADESSO()
        c.execute('INSERT OR REPLACE INTO sedi_wauc(' + ','.join(d) + ') VALUES(' + ','.join('?' * len(d)) + ')', list(d.values()))
        n += 1; coord += d['lat'] is not None
        if tipo == 'CMD' and cid:
            conn += 1; sigla = (c.execute('SELECT sigla FROM comandi WHERE id=?', (cid,)).fetchone()[0] or '').upper()
            if d['codice'].upper() == sigla and sigla: esatte.add(cid); c.execute('UPDATE comandi SET wauc_sede_id=? WHERE id=?', (d['id'], cid))
            elif cid not in esatte: c.execute('UPDATE comandi SET wauc_sede_id=? WHERE id=? AND (wauc_sede_id IS NULL OR wauc_sede_id=?)', (d['id'], cid, d['id']))
    _segna_sync(c, 'sedi')
    return dict(sedi=n, comandi=c.execute("SELECT COUNT(*) FROM sedi_wauc WHERE cod_tipo_dipartimento='CMD'").fetchone()[0],
                collegati=c.execute('SELECT COUNT(*) FROM comandi WHERE wauc_sede_id IS NOT NULL').fetchone()[0], con_coordinate=coord)

def sincronizza_catalogo(c):
    """Specializzazioni e qualifiche insieme. Ritorna (n_specializzazioni, n_qualifiche); solleva eccezione se WAUC non risponde."""
    return sincronizza_specializzazioni(c), sincronizza_qualifiche(c)

def stato_anagrafiche(c):
    """Riepilogo per Configurazione: numeri e data dell'ultimo aggiornamento di sedi, qualifiche, specializzazioni."""
    q = lambda sql: c.execute(sql).fetchone()[0]
    quando = lambda k: (c.execute('SELECT eseguita_il FROM wauc_sync WHERE chiave=?', (k,)).fetchone() or [None])[0]
    return dict(
        sedi=dict(n=q('SELECT COUNT(*) FROM sedi_wauc'), comandi=q("SELECT COUNT(*) FROM sedi_wauc WHERE cod_tipo_dipartimento='CMD'"),
                  collegati=q('SELECT COUNT(*) FROM comandi WHERE wauc_sede_id IS NOT NULL'), totale_comandi=q('SELECT COUNT(*) FROM comandi'), quando=quando('sedi')),
        qualifiche=dict(n=q('SELECT COUNT(*) FROM qualifiche_wauc'), quando=quando('qualifiche') or quando('catalogo')),
        specializzazioni=dict(n=q('SELECT COUNT(*) FROM specializzazioni WHERE aggiornata_il IS NOT NULL'), utenti=q("SELECT COUNT(*) FROM specializzazioni WHERE fonte='utente'"),
                              quando=quando('specializzazioni') or quando('catalogo')))

def assicura_catalogo(c, ore=24):
    """Scarica l'elenco completo di specializzazioni/qualifiche da WAUC se non è mai stato caricato o ha più di `ore` ore (un tentativo ogni 10 minuti
    al massimo; se WAUC non risponde si prosegue senza errori)."""
    if not config.WAUC_ATTIVO: return
    def quando(k):
        r = c.execute('SELECT eseguita_il FROM wauc_sync WHERE chiave=?', (k,)).fetchone()
        return datetime.datetime.fromisoformat(r[0]) if r else None
    def segna(k): c.execute('INSERT INTO wauc_sync VALUES(?,?) ON CONFLICT(chiave) DO UPDATE SET eseguita_il=excluded.eseguita_il', (k, ADESSO()))
    ora = datetime.datetime.now(); ok, tent = quando('catalogo'), quando('catalogo_tentativo')
    if (ok and ora - ok < datetime.timedelta(hours=ore)) or (tent and ora - tent < datetime.timedelta(minutes=10)): return
    segna('catalogo_tentativo')
    try: sincronizza_catalogo(c); segna('catalogo')
    except Exception as e: log.warning('Catalogo WAUC non aggiornato: %s', e)

def aggiungi_specializzazione(c, uid, codice, descrizione, data=None):
    """Specializzazione assente dall'elenco WAUC aggiunta dall'utente: entra nel catalogo (fonte 'utente', da tradurre poi dall'admin) e viene spuntata.
    Ritorna 'nuova' | 'esistente' (era già nel catalogo, è stata solo spuntata) | 'gia_tua' (già presente tra le sue da WAUC)."""
    if c.execute("SELECT 1 FROM specializzazioni_utente WHERE utente_id=? AND codice=? AND origine='wauc'", (uid, codice)).fetchone(): return 'gia_tua'
    esito = 'esistente'
    if not c.execute('SELECT 1 FROM specializzazioni WHERE codice=?', (codice,)).fetchone():
        c.execute("INSERT INTO specializzazioni(codice,descrizione,aggiornata_il,fonte) VALUES(?,?,?, 'utente')", (codice, descrizione, ADESSO())); esito = 'nuova'
    desc = c.execute('SELECT descrizione FROM specializzazioni WHERE codice=?', (codice,)).fetchone()[0] or descrizione
    c.execute("INSERT OR REPLACE INTO specializzazioni_utente(utente_id,codice,descrizione,origine,inizio) VALUES(?,?,?, 'manuale', ?)", (uid, codice, desc, data))
    return esito

def salva_anagrafica(c, uid, ex):
    """Memorizza tutti i dati ricevuti da WAUC (tabella anagrafica_wauc)."""
    ex = {**ex, 'ultima_sync': ADESSO()}
    c.execute('INSERT OR REPLACE INTO anagrafica_wauc(utente_id,' + ','.join(ex) + ') VALUES(?,' + ','.join('?' * len(ex)) + ')', (uid, *ex.values()))

def salva_specializzazioni(c, uid, specs):
    """Aggiorna le specializzazioni provenienti da WAUC (con date di validità); quelle spuntate a mano dall'utente restano."""
    registra_specializzazioni(c, [(s[0], s[1]) for s in specs])
    c.execute("DELETE FROM specializzazioni_utente WHERE utente_id=? AND origine='wauc'", (uid,))
    for cod, desc, ini, fin in specs:
        c.execute("INSERT OR REPLACE INTO specializzazioni_utente(utente_id,codice,descrizione,origine,inizio,fine) VALUES(?,?,?, 'wauc', ?,?)", (uid, cod, desc, ini or None, fin or None))

def profila(c, u):
    """Chiamata al login. Se la persona è in WAUC aggiorna sempre anagrafica e specializzazioni; compila i dati del profilo solo se non ancora
    confermato dall'utente. Ritorna (origine, errore)."""
    origine, d, specs, err = trova(c, u['email'])
    if origine == 'wauc': salva_specializzazioni(c, u['id'], specs); salva_anagrafica(c, u['id'], d['extra'])
    if origine and not u['profilo_confermato']:
        cid, dist = risolvi_sede(c, d)
        nuovi = {k: d.get(k) for k in CAMPI if d.get(k) and k != 'distaccamento'}
        if dist: nuovi['distaccamento'] = dist
        if cid: nuovi['comando_id'] = cid
        ex = d.get('extra') or {}
        for k_u, k_w in (('turno', 'turno'), ('salto_turno', 'salto_turno'), ('cod_tipo_personale', 'cod_tipo_personale'), ('tipo_personale', 'desc_tipo_personale'), ('cod_qualifica', 'cod_qualifica'), ('cod_gruppo', 'cod_gruppo')):
            if ex.get(k_w): nuovi[k_u] = ex[k_w]
        nuovi['origine_profilo'] = origine
        c.execute('UPDATE utenti SET ' + ','.join(f'{k}=?' for k in nuovi) + ' WHERE id=?', (*nuovi.values(), u['id']))
    return origine, err

def salva_in_organico(c, u_email, v, comando_nome):
    """Il profilo confermato dall'utente alimenta/aggiorna l'organico locale."""
    c.execute('INSERT INTO organico(email,nome,cognome,matricola,qualifica,comando,distaccamento,telefono,importato_il) VALUES(?,?,?,?,?,?,?,?,?) '
              'ON CONFLICT(email) DO UPDATE SET nome=excluded.nome,cognome=excluded.cognome,matricola=excluded.matricola,qualifica=excluded.qualifica,'
              'comando=excluded.comando,distaccamento=excluded.distaccamento,telefono=excluded.telefono',
              (u_email, v['nome'], v['cognome'], v['matricola'] or None, v['qualifica'] or None, comando_nome, v['distaccamento'] or None, v['telefono'] or None, ADESSO()))
