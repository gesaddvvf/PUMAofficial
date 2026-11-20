"""Libretto di formazione e requisiti, con le stesse regole del sito gesaddvvf.github.io/PUMA (reportindividuale.html):

  attività    = addestramenti collettivi (registrazioni), individuali, interventi reali (gli interventi non hanno ore)
  per corso   = attività del corso nel periodo [anno - Delta anni, anno]; ore svolte, ore in collettivo, giorni
  requisito   = ore >= Ore minime  e  ore collettive >= Ore minime × quota collettive  → «in regola» (ok) / «non in regola» (ko);
                senza Ore minime nel foglio Formazione → «nd»
  manovre     = previste del corso (Manovre_PREVISTE); una manovra (C) vale in qualunque addestramento della persona nel periodo,
                le altre solo nelle attività del corso; le (N) sono attività generiche e non sono manovre previste
  categoria   = somma dei requisiti dei corsi in possesso della categoria (es. SAF), interventi della categoria compresi"""
import json, re
from datetime import date, datetime
from . import corsi as C
from .foglio import norm

ORE_MAX = 168


def _ore(inizio, fine):
    try:
        a, b = datetime.fromisoformat(inizio), datetime.fromisoformat(fine)
    except (TypeError, ValueError): return None
    h = (b - a).total_seconds() / 3600
    return h if 0 < h <= ORE_MAX else None


class Catalogo:
    """Tipologie e manovre caricate una volta per richiesta."""
    def __init__(self, d):
        self.d = d
        self.tip = {r['id']: dict(r) for r in C.tipologie(d)}
        for t in self.tip.values():
            t['eq'] = t['equivale_a'] or t['id']; t['previste'] = []
        self.manovre = {}
        for m in d.execute('SELECT * FROM puma_manovre ORDER BY livello_id, ordine'):
            m = dict(m); m['lettera'] = (m.get('lettera') or '').upper()
            m['chiavi'] = {k for k in (norm(m['nome']), norm(m.get('testo')), norm(m.get('codice')), norm(re.sub(r'\s*\([A-Z]\)\s*$', '', m.get('testo') or ''))) if len(k) >= 4}
            self.manovre[m['id']] = m
            if m['lettera'] != 'N' and m['livello_id'] in self.tip: self.tip[self.tip[m['livello_id']]['eq']]['previste'].append(m)
        self.per_settore = {}
        for t in self.tip.values(): self.per_settore.setdefault((t['settore'] or '').upper(), []).append(t['id'])

    def eq(self, lid): return self.tip[lid]['eq'] if lid in self.tip else lid

    def riconosci(self, testi):
        """Nomi o codici di manovre (come salvati da individuali e programmazione) → id delle manovre previste."""
        out = set()
        for t in testi or []:
            k = norm(t)
            if not k: continue
            for m in self.manovre.values():
                if k in m['chiavi']: out.add(m['id'])
        return out


def attivita(cat, email):
    """Attività di una persona (dict) con ore, anno, corsi e manovre riconosciute."""
    d = cat.d; att = []
    for r in d.execute("""SELECT e.*, c.convalidato FROM puma_checkin c JOIN puma_eventi e ON e.id=c.evento_id WHERE c.username=?""", (email,)):
        dt = date.fromisoformat(r['data'])
        att.append(dict(tipo='collettivo', data=dt, anno=dt.year, giorno=r['data'], ore=_ore(f"{r['data']}T{r['ora_inizio'] or '00:00'}", f"{r['data']}T{r['ora_fine'] or '00:00'}"),
                        corsi={cat.eq(r['livello_id'])} if r['livello_id'] else set(), manovre=cat.riconosci(json.loads(r['manovre'] or '[]')),
                        titolo=r['cod_add'] or r['titolo'] or r['tipologia'], convalidato=bool(r['convalidato']), settore=(r['tipologia'] or '').upper()))
    for r in d.execute('SELECT * FROM puma_individuali WHERE username=?', (email,)):
        dt = date.fromisoformat(r['inizio'][:10])
        att.append(dict(tipo='individuale', data=dt, anno=dt.year, giorno=r['inizio'][:10], ore=_ore(r['inizio'], r['fine']),
                        corsi={cat.eq(r['livello_id'])} if r['livello_id'] else set(), manovre=cat.riconosci(json.loads(r['manovre'] or '[]')),
                        titolo=(r['descrizione'] or '') or (cat.tip.get(r['livello_id'], {}).get('nome') or r['tipologia']), convalidato=True, settore=(r['tipologia'] or '').upper()))
    for r in d.execute('SELECT * FROM puma_interventi WHERE username=?', (email,)):
        dt = date.fromisoformat(r['data'][:10])
        att.append(dict(tipo='intervento', data=dt, anno=dt.year, giorno=r['data'][:10], ore=None, corsi=set(), manovre=set(),
                        titolo=r['descrizione'] or r['macro'], convalidato=True, settore=(r['macro'] or '').upper()))
    for a in att:
        if not a['settore'] and a['corsi']: a['settore'] = (cat.tip.get(next(iter(a['corsi'])), {}).get('settore') or '').upper()
    return sorted(att, key=lambda a: a['data'])


def _somma(lista):
    return dict(n=len(lista), giorni=len({a['giorno'] for a in lista}), ore=sum(a['ore'] or 0 for a in lista), senza_ore=sum(1 for a in lista if a['ore'] is None))


def riepilogo_anno(att, y):
    l = [a for a in att if a['anno'] == y]; add = [a for a in l if a['tipo'] != 'intervento']
    return dict(tot=_somma(add), coll=_somma([a for a in add if a['tipo'] == 'collettivo']), ind=_somma([a for a in add if a['tipo'] == 'individuale']),
                int=_somma([a for a in l if a['tipo'] == 'intervento']), mesi=[sum(a['ore'] or 0 for a in add if a['data'].month == m + 1) for m in range(12)])


def riepilogo_corsi(cat, att, possesso, y):
    """Una riga per corso coinvolto (in possesso o con attività nel periodo)."""
    finestra = lambda a, t: y - (t['delta_anni'] or 0) <= a['anno'] <= y
    coinvolti = {lid for lid in possesso if lid in cat.tip and cat.tip[lid]['corso']}
    for a in att:
        for lid in a['corsi']:
            if lid in cat.tip and cat.tip[lid]['corso'] and finestra(a, cat.tip[lid]): coinvolti.add(lid)
    out = []
    for lid in coinvolti:
        t = cat.tip[lid]
        nel = [a for a in att if lid in a['corsi'] and finestra(a, t)]
        add = [a for a in nel if a['tipo'] != 'intervento']; coll = [a for a in add if a['tipo'] == 'collettivo']
        ore, ore_coll = sum(a['ore'] or 0 for a in add), sum(a['ore'] or 0 for a in coll)
        fatte = {}
        for a in att:
            if a['tipo'] == 'intervento' or not finestra(a, t): continue
            for mid in a['manovre']:
                m = cat.manovre[mid]
                if cat.eq(m['livello_id']) != lid: continue
                if a not in nel and m['lettera'] != 'C': continue
                f = fatte.setdefault(mid, dict(n=0, ultima=None)); f['n'] += 1; f['ultima'] = max(f['ultima'] or a['data'], a['data'])
        # (C) nei corsi che la prevedono: il collettivo stesso è la manovra (es. «Addestramento provinciale di gruppo (C)»)
        for m in t['previste']:
            if m['lettera'] == 'C' and coll and m['id'] not in fatte and re.search(r'di gruppo|collettiv', m['nome'], re.I):
                fatte[m['id']] = dict(n=len(coll), ultima=max(a['data'] for a in coll))
        coll_min = t['ore_minime'] * t['quota_collettive'] if t['ore_minime'] and t['quota_collettive'] else None
        stato = 'nd'
        if t['ore_minime']: stato = 'ok' if ore >= t['ore_minime'] - 1e-6 and (coll_min is None or ore_coll >= coll_min - 1e-6) else 'ko'
        out.append(dict(t=t, ore=ore, ore_coll=ore_coll, ore_anno=sum(a['ore'] or 0 for a in add if a['anno'] == y), coll_min=coll_min, stato=stato,
                        giorni=len({a['giorno'] for a in add}), n_att=len(add), n_int=len(nel) - len(add), fatte=fatte,
                        da_fare=[m for m in t['previste'] if m['id'] not in fatte], dal=y - (t['delta_anni'] or 0), possesso=lid in possesso,
                        origine=possesso.get(lid), attivita=add))
    return sorted(out, key=lambda r: (r['t']['ordine'], r['t']['sovraordinazione'] or 999, r['t']['nome']))


def riepilogo_settori(cat, att, righe, y):
    """Requisiti per categoria (SAF, TAS...): ore dei corsi + interventi della categoria contro la somma delle ore minime dei corsi posseduti."""
    out = {}
    for r in righe: out.setdefault(r['t']['settore'] or 'VARIE', []).append(r)
    ris = []
    for sett, rr in out.items():
        req = [r for r in rr if r['possesso'] and r['t']['ore_minime']]
        anni = max([r['t']['delta_anni'] or 0 for r in rr] + [0])
        lids = {r['t']['id'] for r in rr}
        add = [a for a in att if a['tipo'] != 'intervento' and a['corsi'] & lids and y - anni <= a['anno'] <= y]
        intv = [a for a in att if a['tipo'] == 'intervento' and a['anno'] == y and a['settore'] == sett.upper()]
        ore_add, ore_coll = sum(a['ore'] or 0 for a in add), sum(a['ore'] or 0 for a in add if a['tipo'] == 'collettivo')
        min_tot = sum(r['t']['ore_minime'] for r in req); coll_tot = sum(r['coll_min'] or 0 for r in req)
        stato = 'nd' if not min_tot else ('ok' if ore_add >= min_tot - 1e-6 and ore_coll >= coll_tot - 1e-6 else 'ko')
        nome = cat.d.execute('SELECT nome FROM puma_settori WHERE codice=?', (sett,)).fetchone()
        ris.append(dict(codice=sett, nome=nome[0] if nome else sett, righe=rr, ore=ore_add, ore_coll=ore_coll, interventi=len(intv), min_tot=min_tot,
                        coll_tot=coll_tot, stato=stato, manca=max(0, min_tot - ore_add, coll_tot - ore_coll), dal=y - anni))
    return sorted(ris, key=lambda s: min(r['t']['ordine'] for r in s['righe']))


def libretto(d, utente, y, cat=None):
    """Tutto il necessario per il report individuale di una persona (utente = riga di utenti)."""
    cat = cat or Catalogo(d)
    att = attivita(cat, utente['email'])
    poss = C.possesso(d, utente)
    righe = riepilogo_corsi(cat, att, poss, y)
    return dict(att=att, anno=riepilogo_anno(att, y), corsi=righe, settori=riepilogo_settori(cat, att, righe, y), possesso=poss,
                anni=sorted({a['anno'] for a in att} | {date.today().year}, reverse=True))


def persone_ente(d, comandi):
    """Utenti attivi delle sedi indicate (None = tutte)."""
    q = "SELECT u.*, k.nome AS comando FROM utenti u LEFT JOIN comandi k ON k.id=u.comando_id WHERE u.stato='attivo'"
    if comandi is None: return d.execute(q + ' ORDER BY u.cognome, u.nome').fetchall()
    if not comandi: return []
    return d.execute(q + ' AND u.comando_id IN (%s) ORDER BY u.cognome, u.nome' % ','.join('?' * len(comandi)), comandi).fetchall()
