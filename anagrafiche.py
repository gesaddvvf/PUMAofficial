"""Sedi di appartenenza (Comandi, Direzioni regionali, CON, SOCAV) con i dati di FireOps VVF (dati/sedi_fireops.json).

All'avvio i contatti vengono copiati nella tabella comandi SOLO nei campi vuoti: le modifiche fatte a mano da un amministratore
(Area Comando → Schede dei comandi) restano. La Direzione di ogni Comando invece segue sempre FireOps.
Per sovrascrivere tutto:  python manage.py aggiorna-sedi --forza"""
import json, os, datetime
import config

FILE = os.path.join(config.BASE_DIR, 'dati', 'sedi_fireops.json')
CAMPI = ('telefono', 'telefono_so', 'email', 'pec', 'email_so', 'pec_so', 'indirizzo', 'cap', 'comune', 'lat', 'lon',
         'sito_web', 'sito_intranet', 'canale_radio', 'nue', 'regione')


def _dati():
    with open(FILE, encoding='utf-8') as f: return json.load(f)


def _scrivi(c, cid, d, forza):
    riga = c.execute('SELECT * FROM comandi WHERE id=?', (cid,)).fetchone()
    v = {k: d.get(k) for k in CAMPI if k in d and d.get(k) not in (None, '') and (forza or riga[k] in (None, ''))}
    if v:
        c.execute('UPDATE comandi SET ' + ','.join(f'{k}=?' for k in v) + ", fonte_contatti='fireops' WHERE id=?", (*v.values(), cid))
    return bool(v)


def aggiorna_sedi(c, forza=False):
    """Ritorna dict(comandi, direzioni, nazionali, aggiornati). Non solleva eccezioni se il file manca."""
    if not os.path.exists(FILE): return dict(comandi=0, direzioni=0, nazionali=0, aggiornati=0)
    d = _dati(); agg = 0
    dirz = {r['nome']: r['id'] for r in c.execute('SELECT id, nome FROM puma_direzioni')}
    for x in d['comandi']:
        r = c.execute("SELECT id FROM comandi WHERE upper(sigla)=? AND tipo='comando'", (x['sigla'].upper(),)).fetchone()
        if not r:
            cid = c.execute("INSERT INTO comandi(nome, sigla, tipo) VALUES(?,?, 'comando')", (x['nome'], x['sigla'])).lastrowid
        else: cid = r['id']
        agg += _scrivi(c, cid, x, forza)
        if x.get('direzione') in dirz:
            c.execute('INSERT INTO puma_comando_dir(comando_id, direzione_id) VALUES(?,?) ON CONFLICT(comando_id) DO UPDATE SET direzione_id=excluded.direzione_id',
                      (cid, dirz[x['direzione']]))
    for x in d['direzioni']:
        if x['nome'] not in dirz:
            dirz[x['nome']] = c.execute('INSERT INTO puma_direzioni(nome) VALUES(?)', (x['nome'],)).lastrowid
        nome = 'Direzione Regionale ' + x['nome']
        r = c.execute("SELECT id FROM comandi WHERE nome=?", (nome,)).fetchone()
        cid = r['id'] if r else c.execute("INSERT INTO comandi(nome, tipo, regione) VALUES(?, 'direzione', ?)", (nome, x['nome'])).lastrowid
        c.execute("UPDATE comandi SET tipo='direzione' WHERE id=?", (cid,))
        c.execute('INSERT INTO puma_comando_dir(comando_id, direzione_id) VALUES(?,?) ON CONFLICT(comando_id) DO UPDATE SET direzione_id=excluded.direzione_id',
                  (cid, dirz[x['nome']]))
        agg += _scrivi(c, cid, x, forza)
    for x in d['nazionali']:
        r = c.execute("SELECT id FROM comandi WHERE sigla=? AND tipo='nazionale'", (x['sigla'],)).fetchone()
        if r: agg += _scrivi(c, r['id'], x, forza)
    c.execute('INSERT INTO wauc_sync VALUES(?,?) ON CONFLICT(chiave) DO UPDATE SET eseguita_il=excluded.eseguita_il',
              ('sedi_fireops', datetime.datetime.now().isoformat(timespec='seconds')))
    return dict(comandi=len(d['comandi']), direzioni=len(d['direzioni']), nazionali=len(d['nazionali']), aggiornati=agg)


def confinanti(sigla):
    """Comandi confinanti (nomi) secondo FireOps: servono per mostrare gli addestramenti dei Comandi vicini."""
    for x in _dati()['comandi']:
        if x['sigla'].upper() == (sigla or '').upper(): return x.get('confinanti', [])
    return []
