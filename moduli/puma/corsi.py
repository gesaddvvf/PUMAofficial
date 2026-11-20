"""Catalogo delle tipologie (corsi) e corsi in possesso di ogni persona, con le regole del sito gesaddvvf.github.io/PUMA:
  - corsi in possesso = specializzazioni WAUC collegate (codici_wauc) + foglio Elenco_Filtrato + corsi «di tutti»
    (SAF Competenze primarie, TPSS); SAF1A conta come Competenze primarie (equivale_a)."""
import json, os, re
from .foglio import norm

DATI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dati')


def seed_tipologie(d):
    """Carica (una volta, poi solo i campi vuoti) tipologie, categorie e collegamenti WAUC da dati/tipologie.json."""
    with open(os.path.join(DATI, 'tipologie.json'), encoding='utf-8') as f: t = json.load(f)
    for cod, nome in t['categorie']:
        d.execute('INSERT INTO puma_settori(codice, nome) VALUES(?,?) ON CONFLICT(codice) DO UPDATE SET nome=excluded.nome', (cod, nome))
    for x in t['tipologie']:
        r = d.execute('SELECT * FROM puma_livelli WHERE nome=?', (x['nome'],)).fetchone()
        if not r:
            d.execute('INSERT INTO puma_livelli(settore, nome, mesi_validita) VALUES(?,?,12)', (x['categoria'], x['nome']))
            r = d.execute('SELECT * FROM puma_livelli WHERE nome=?', (x['nome'],)).fetchone()
        d.execute("""UPDATE puma_livelli SET settore=?, chiave=?, corso=?, di_tutti=?, ordine=?, sigla=COALESCE(sigla, ?),
                     codici_wauc=COALESCE(codici_wauc, ?) WHERE id=?""",
                  (x['categoria'], x['chiave'], x['corso'], x['di_tutti'], x['ordine'], x['sigla'], x['codici_wauc'] or None, r['id']))
    for da, a in t['equivalenti'].items():
        d.execute('UPDATE puma_livelli SET equivale_a=(SELECT id FROM puma_livelli WHERE nome=?) WHERE nome=?', (a, da))


def tipologie(d, solo_corsi=False):
    return d.execute('SELECT l.*, s.nome AS categoria FROM puma_livelli l LEFT JOIN puma_settori s ON s.codice=l.settore '
                     + ('WHERE l.corso=1 ' if solo_corsi else '') + 'ORDER BY l.ordine, l.sovraordinazione, l.nome').fetchall()


def equivalente(d, lid):
    r = d.execute('SELECT equivale_a FROM puma_livelli WHERE id=?', (lid,)).fetchone()
    return r['equivale_a'] if r and r['equivale_a'] else lid


def possesso(d, utente):
    """{id tipologia: origine} dei corsi in possesso. utente = riga di utenti (email, nome, cognome, id)."""
    out = {}
    for r in d.execute('SELECT id FROM puma_livelli WHERE di_tutti=1'): out[r['id']] = 'di tutti'
    codici = {}
    for r in d.execute('SELECT id, codici_wauc FROM puma_livelli WHERE codici_wauc IS NOT NULL'):
        for c in r['codici_wauc'].split(','):
            if c.strip(): codici.setdefault(c.strip().upper(), []).append(r['id'])
    for s in d.execute('SELECT codice, origine FROM specializzazioni_utente WHERE utente_id=?', (utente['id'],)):
        for lid in codici.get((s['codice'] or '').upper(), []): out[equivalente(d, lid)] = 'WAUC' if s['origine'] == 'wauc' else 'dichiarato'
    # foglio Elenco_Filtrato: per codice fiscale o per cognome e nome
    cf = d.execute('SELECT codice_fiscale FROM puma_persone WHERE utente_id=?', (utente['id'],)).fetchone()
    riga = d.execute('SELECT * FROM puma_possesso_foglio WHERE chiave=?', ('cf:' + cf[0].upper(),)).fetchone() if cf else None
    if not riga:
        for k in ('n:' + norm(f"{utente['cognome'] or ''}{utente['nome'] or ''}"), 'n:' + norm(f"{utente['nome'] or ''}{utente['cognome'] or ''}")):
            riga = d.execute('SELECT * FROM puma_possesso_foglio WHERE chiave=?', (k,)).fetchone()
            if riga: break
    if riga and riga['corsi']:
        for v in re.split(r'\n|;|,(?![^()]*\))', riga['corsi']):
            lid = trova(d, v)
            if lid: out.setdefault(equivalente(d, lid), 'foglio PUMA')
    return out


def trova(d, testo):
    k = norm(testo)
    if len(k) < 2: return None
    k2 = norm(re.sub(r'\(.*?\)', ' ', testo or ''))
    righe = d.execute('SELECT id, nome, sigla, profilazione FROM puma_livelli').fetchall()
    for r in righe:
        if k in (norm(r['nome']), norm(r['profilazione'])): return r['id']
    for r in righe:
        if k2 and k2 == norm(re.sub(r'\(.*?\)', ' ', r['nome'])): return r['id']
    best = None
    for r in righe:
        for kk in (norm(r['nome']), norm(r['profilazione'])):
            if len(kk) >= 6 and kk in k and (not best or len(kk) > best[1]): best = (r['id'], len(kk))
    return best[0] if best else None
