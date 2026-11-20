"""Import dal foglio Google «PUMA VVF Database Personale» scaricato come Excel (File → Scarica → Microsoft Excel .xlsx).

Fogli letti (come fa il sito gesaddvvf.github.io/PUMA):
  Formazione        requisiti di ogni tipologia: Sigla, Tipologia, Categoria, Corsi (Profilazione), Delta anni, Ore minime, Collettive %, Sovraordinazione
  Manovre_PREVISTE  manovre previste: A corso (sigla o tipologia), B UID, C codice, D ciclo, E manovra, F testo completo con lettera (A/B/C/N)
  Elenco_Filtrato   corsi in possesso di ogni persona (Cognome Nome - Codice Fiscale, Appartenenza, Qualifica, Corsi in possesso)
I dati personali di altri fogli (registrazioni, piani) NON vengono letti.
Lettore .xlsx con la sola libreria standard (zip + xml): nessuna installazione."""
import datetime, re, unicodedata, zipfile
import xml.etree.ElementTree as ET

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def _col(rif):
    n = 0
    for ch in re.match(r'[A-Z]+', rif).group(0): n = n * 26 + ord(ch) - 64
    return n - 1


def leggi_xlsx(percorso, fogli=None):
    """{nome foglio: [righe]} con i valori come testo (numeri come float). fogli = elenco di nomi da leggere (None = tutti)."""
    z = zipfile.ZipFile(percorso)
    condivise = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
            condivise.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).findall('rel:Relationship', NS)}
    out = {}
    for s in wb.find('m:sheets', NS).findall('m:sheet', NS):
        nome = s.get('name')
        if fogli is not None and nome not in fogli: continue
        dest = rels[s.get('{%s}id' % NS['r'])].lstrip('/')
        dest = dest if dest.startswith('xl/') else 'xl/' + dest
        righe = []
        for ev, el in ET.iterparse(z.open(dest)):
            if el.tag != '{%s}row' % NS['m']: continue
            riga = []
            for c in el.findall('m:c', NS):
                i = _col(c.get('r')); t = c.get('t'); v = c.find('m:v', NS)
                if t == 's': val = condivise[int(v.text)] if v is not None else ''
                elif t == 'inlineStr': val = ''.join(x.text or '' for x in c.iter('{%s}t' % NS['m']))
                elif t in ('str', 'e'): val = v.text if v is not None else ''
                elif t == 'b': val = 'VERO' if v is not None and v.text == '1' else 'FALSO'
                else:
                    val = '' if v is None else v.text
                    try: val = float(val)
                    except (TypeError, ValueError): pass
                while len(riga) < i: riga.append('')
                riga.append(val)
            righe.append(riga); el.clear()
        out[nome] = righe
    return out


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower())


def _t(v):
    if isinstance(v, float): return ('%d' % v) if v.is_integer() else str(v)
    return str(v or '').strip()


def _ore(v):
    """«Ore Minime (in giorni)»: durata di Sheets (1 = 24 ore) oppure «36:00:00» / «36»."""
    if v in ('', None): return None
    if isinstance(v, float): return round(v * 24, 4) if v < 50 else v
    s = str(v).strip().replace(',', '.')
    m = re.match(r'^(\d+):(\d{1,2})(?::\d{1,2})?$', s)
    if m: return int(m.group(1)) + int(m.group(2)) / 60
    try: return float(s)
    except ValueError: return None


def _pct(v):
    if v in ('', None): return None
    if isinstance(v, float): return v / 100 if v > 1 else v
    s = str(v).strip().replace('%', '').replace(',', '.')
    try: x = float(s)
    except ValueError: return None
    return x / 100 if x > 1 else x


RE_LETTERA = re.compile(r'\s*\(([A-Za-z])\)\s*$')
RE_CF = re.compile(r'\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b', re.I)


def _trova_livello(d, testo, per_sigla=True):
    """Tipologia di PUMA da un testo del foglio (sigla, nome tipologia o corso di profilazione)."""
    k = norm(testo)
    if not k: return None
    for r in d.execute('SELECT id, nome, sigla, profilazione FROM puma_livelli'):
        if norm(r['nome']) == k or (r['profilazione'] and norm(r['profilazione']) == k): return r['id']
    if per_sigla:
        for r in d.execute('SELECT id, sigla FROM puma_livelli WHERE sigla IS NOT NULL'):
            if norm(r['sigla']) == k: return r['id']
    return None


def importa(d, percorso):
    """Importa Formazione, Manovre_PREVISTE ed Elenco_Filtrato. Ritorna un riepilogo (dict)."""
    fogli = leggi_xlsx(percorso, {'Formazione', 'Manovre_PREVISTE', 'Elenco_Filtrato'})
    ris = dict(fogli=sorted(fogli), tipologie=0, nuove=0, manovre=0, manovre_senza_corso=0, persone=0)
    adesso = datetime.datetime.now().isoformat(timespec='seconds')
    # --- Formazione
    rows = fogli.get('Formazione') or []
    hi = next((i for i, r in enumerate(rows) if any(norm(c) == 'sigla' for c in r)), None)
    if hi is not None:
        head = [norm(c) for c in rows[hi]]
        ix = lambda *chiavi: next((i for i, h in enumerate(head) if any(h.startswith(k) or k in h for k in chiavi)), None)
        c = dict(sigla=ix('sigla'), tip=ix('tipologia'), cat=ix('categoria'), prof=ix('corsiprofilazione'), delta=ix('deltaanni'),
                 ore=ix('oreminime'), coll=ix('collettive'), sovra=ix('sovraordinazione'))
        g = lambda r, k: (r[c[k]] if c[k] is not None and c[k] < len(r) else '')
        for r in rows[hi + 1:]:
            tip = _t(g(r, 'tip'))
            if not tip: continue
            cat_testo = _t(g(r, 'cat')) or tip
            cat = d.execute('SELECT codice FROM puma_settori WHERE ?=lower(nome) OR ?=lower(codice)', (cat_testo.lower(), cat_testo.split(' ')[0].lower())).fetchone()
            if not cat:
                codice = re.sub(r'[^A-Z0-9]', '', cat_testo.split('(')[0].upper())[:8] or 'VARIE'
                d.execute('INSERT OR IGNORE INTO puma_settori(codice, nome) VALUES(?,?)', (codice, cat_testo)); cat = (codice,)
            try: delta = max(0, -int(float(_t(g(r, 'delta')) or 0)))
            except ValueError: delta = 0
            try: sovra = float(_t(g(r, 'sovra')).replace(',', '.'))
            except ValueError: sovra = None
            lid = _trova_livello(d, tip, per_sigla=False)
            v = dict(sigla=_t(g(r, 'sigla')) or None, profilazione=_t(g(r, 'prof')) or None, delta_anni=delta, ore_minime=_ore(g(r, 'ore')),
                     quota_collettive=_pct(g(r, 'coll')), sovraordinazione=sovra, da_foglio=adesso)
            if lid:
                d.execute('UPDATE puma_livelli SET ' + ','.join(f'{k}=?' for k in v) + ', settore=? WHERE id=?', (*v.values(), cat[0], lid))
            else:
                d.execute('INSERT INTO puma_livelli(settore, nome, corso, ordine, ' + ','.join(v) + ') VALUES(?,?,1,999,' + ','.join('?' * len(v)) + ')',
                          (cat[0], tip, *v.values())); ris['nuove'] += 1
            ris['tipologie'] += 1
    # --- Manovre_PREVISTE
    rows = fogli.get('Manovre_PREVISTE') or []
    if rows:
        visti = set(); nuove = []
        for r in rows:
            r = [_t(x) for x in r] + [''] * 6
            a, uid, cod, ciclo, man, full = r[:6]
            if not man and not full: continue
            if re.search(r'associazione', a, re.I) or re.fullmatch(r'manovra', man, re.I): continue   # intestazione
            testo = full or ' '.join(x for x in (ciclo, cod, man) if x)
            m = RE_LETTERA.search(testo) or RE_LETTERA.search(man)
            lett = m.group(1).upper() if m else ''
            lid = _trova_livello(d, a)
            if not lid:
                ris['manovre_senza_corso'] += 1; continue
            visti.add(lid); nuove.append((lid, man or testo, cod, ciclo, uid, lett, testo))
        for lid in visti: d.execute('DELETE FROM puma_manovre WHERE livello_id=?', (lid,))
        for n, (lid, nome, cod, ciclo, uid, lett, testo) in enumerate(nuove):
            d.execute('INSERT INTO puma_manovre(livello_id, nome, ordine, codice, ciclo, uid, lettera, testo, da_foglio) VALUES(?,?,?,?,?,?,?,?,1)',
                      (lid, RE_LETTERA.sub('', nome).strip(), n, f'F{n:04d}-{cod}' if cod else f'F{n:04d}', ciclo, uid, lett, testo))
            ris['manovre'] += 1
    # --- Elenco_Filtrato (solo nominativo, appartenenza, qualifica, corsi)
    rows = fogli.get('Elenco_Filtrato') or []
    if rows:
        head = [norm(c) for c in rows[0]]
        col = lambda k: next((i for i, h in enumerate(head) if k in h), None)
        cn, cc, cq, cs = col('cognomenome'), col('appartenenza'), col('qualifica'), col('corsiinpossesso')
        if cn is not None:
            d.execute('DELETE FROM puma_possesso_foglio')
            for r in rows[1:]:
                r = [_t(x) for x in r] + [''] * 20
                raw = r[cn]
                if len(raw) < 3: continue
                m = RE_CF.search(raw); cf = m.group(0) if m else None
                nome = re.sub(r'\s*-?\s*' + (cf or 'ZZZZZZ') + r'.*$', '', raw, flags=re.I).strip(' -')
                chiave = 'cf:' + cf.upper() if cf else 'n:' + norm(nome)
                d.execute('INSERT OR REPLACE INTO puma_possesso_foglio VALUES(?,?,?,?,?,?,?)',
                          (chiave, nome, cf.upper() if cf else None, r[cc] if cc is not None else None, r[cq] if cq is not None else None,
                           r[cs] if cs is not None else '', adesso))
                ris['persone'] += 1
    return ris
