"""Anagrafica del personale dall'API WAUC (intranet). Ricerca per email, estrazione di nome/cognome, comando, qualifica e specializzazioni.
Usa solo la libreria standard. I nomi dei campi dell'API vengono riconosciuti in modo tollerante (vedi CHIAVI): se qualcosa non torna,
`python3 manage.py wauc-test [email]` mostra i campi realmente restituiti."""
import json, ssl, time, re, string, datetime, threading, concurrent.futures, unicodedata, urllib.request, urllib.parse, urllib.error
import config

CACHE_SEC = 600
_cache = {}

CHIAVI = {   # chiavi (normalizzate: minuscolo, solo lettere/cifre) accettate per ogni dato
    'email': ['email', 'mail', 'emailistituzionale', 'emailvvf', 'indirizzoemail', 'posta', 'emailaziendale'],
    'nome': ['nome', 'firstname', 'name'],
    'cognome': ['cognome', 'lastname', 'surname'],
    'matricola': ['matricola', 'codicematricola', 'nmatricola'],
    'qualifica': ['qualifica', 'descqualifica', 'descrizionequalifica', 'desqualifica', 'codicequalifica', 'codqualifica'],
    # struttura reale dei record: vedi estrai_campi(); queste chiavi servono solo come ripiego per record con struttura piatta
    'comando': ['comando', 'comandoprovinciale', 'desccomando', 'descrizionecomando', 'nomecomando', 'provincia', 'descprovincia', 'descrizioneprovincia', 'nomeprovincia'],
    'distaccamento': ['distaccamento', 'descdistaccamento', 'descrizionedistaccamento'],
    'telefono': ['telefono', 'cellulare', 'cell', 'tel', 'telefonocellulare'],
}
SPEC_CODICE = ['codice', 'cod_specializzazione', 'codicespecializzazione', 'cod', 'codspecializzazione']
SPEC_DESC = ['descrizione', 'desc_specializzazione', 'descspecializzazione', 'descrizionespecializzazione', 'desc']

def norm(s): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower())

def _get(url, params=None):
    if config.WAUC_FINTO:   # modalità prova: risposte simulate da prova/wauc_finto.json, con la stessa struttura dell'API reale
        from prova import wauc_finto
        return wauc_finto.risposta(url, params or {})
    if params: url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'accept': 'application/json'})
    ctx = None if config.WAUC_VERIFY_SSL else ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=config.WAUC_TIMEOUT, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))

def _unwrap(d):
    if isinstance(d, list): return d
    if isinstance(d, dict): return d.get('value', d.get('data', []))
    return []

# Valori incontrati nei record scaricati (alimentano le scelte del profilo: «solo valori trovati in WAUC»); svuotati da svuota_osservati()
_lock = threading.Lock()
OSSERVATI = {'tipo_personale': {}, 'turno': {}, 'salto_turno': {}, 'qualifiche': {}, 'distaccamenti': {}}

def _osserva(sede, recs):
    with _lock:
        for r in recs:
            ex = estrai_campi(r)
            if ex['cod_tipo_personale']: OSSERVATI['tipo_personale'][ex['cod_tipo_personale']] = ex['desc_tipo_personale']
            if ex['turno']: OSSERVATI['turno'][ex['turno']] = ''
            if ex['salto_turno']: OSSERVATI['salto_turno'][ex['salto_turno']] = ''
            if ex['cod_qualifica']: OSSERVATI['qualifiche'][(ex['cod_qualifica'], ex['cod_gruppo'])] = (ex['desc_qualifica'], ex['nome_qualifica'], ex['cod_settore'], ex['desc_gruppo'], ex['ambito'])
            if ex['cod_distaccamento']: OSSERVATI['distaccamenti'][(ex['cod_sede'] or sede, ex['cod_distaccamento'])] = ex['desc_sede']

def svuota_osservati():
    with _lock:
        copia = {k: dict(v) for k, v in OSSERVATI.items()}
        for v in OSSERVATI.values(): v.clear()
    return copia

def _fetch(sede):
    """Scarica il personale di una sede (senza cache)."""
    recs = [r for r in _unwrap(_get(f'{config.WAUC_HTTP}/api/Personale', {'codiciSede': sede})) if isinstance(r, dict)]
    _osserva(sede, recs); return recs

def fetch_personale(sede):
    t = time.time(); v = _cache.get(sede)
    if v and t - v[0] < CACHE_SEC: return v[1]
    recs = _fetch(sede); _cache[sede] = (t, recs); return recs

def scopri_sedi(sigle, lavoratori=8):
    """Interroga ogni codice sede: ritorna {codice: numero persone, oppure None se l'interrogazione è fallita}."""
    def uno(s):
        try: return s, len(_fetch(s))
        except Exception: return s, None
    with concurrent.futures.ThreadPoolExecutor(max_workers=lavoratori) as ex: return dict(ex.map(uno, sigle))

def fetch_specializzazioni_lookup():
    return _unwrap(_get(f'{config.WAUC_HTTPS}/api/Specializzazioni'))

def _testo(v):
    if isinstance(v, dict):
        for k in ('descrizione', 'desc', 'nome', 'codice'):
            if v.get(k): return str(v[k]).strip()
        return ''
    return '' if v is None else str(v).strip()

def _campo(rec, nome):
    cand = CHIAVI[nome]; mappa = {norm(k): v for k, v in rec.items()}
    for k in cand:
        t = _testo(mappa.get(k))
        if t: return t
    return ''

def _coppia(it):
    """(codice maiuscolo, descrizione) da una voce di specializzazione (stringa o dict); codice vuoto se non riconosciuta."""
    if isinstance(it, str): return it.strip().upper(), ''
    if not isinstance(it, dict): return '', ''
    m = {norm(a): b for a, b in it.items()}
    cod = next((str(m[norm(x)]) for x in SPEC_CODICE if m.get(norm(x))), '')
    desc = next((str(m[norm(x)]) for x in SPEC_DESC if m.get(norm(x))), '')
    return cod.strip().upper(), desc.strip()

def _data_iso(v):
    """'31/12/2030' o '2030-12-31...' -> '2030-12-31'; '' se vuota/non riconosciuta."""
    s = _s(v)[:10]
    if not s: return ''
    try: return datetime.datetime.strptime(s, '%d/%m/%Y').date().isoformat()
    except ValueError: pass
    try: return datetime.date.fromisoformat(s).isoformat()
    except ValueError: return ''

def _specs(rec):
    """TUTTE le specializzazioni del record: lista di (codice, descrizione, inizio, fine) con date ISO ('' = senza scadenza).
    Se un codice compare più volte si tiene la voce senza scadenza o, altrimenti, quella che scade più tardi."""
    out = {}
    for k, v in rec.items():
        if 'special' in norm(k) and isinstance(v, list):
            for it in v:
                cod, desc = _coppia(it)
                if not cod: continue
                ini, fin = (_data_iso(_g(it, 'dataInizioValidita')), _data_iso(_g(it, 'dataFineValidita'))) if isinstance(it, dict) else ('', '')
                vecchio = out.get(cod)
                if vecchio is None or (vecchio[3] and (not fin or fin > vecchio[3])): out[cod] = (cod, desc, ini, fin)
    return list(out.values())

def catalogo_specializzazioni():
    """Elenco completo delle specializzazioni esistenti in WAUC: lista di (codice, descrizione)."""
    out = {}
    for it in fetch_specializzazioni_lookup():
        cod, desc = _coppia(it)
        if cod: out.setdefault(cod, desc)
    return list(out.items())

def catalogo_specializzazioni_completo():
    """Catalogo specializzazioni con le date di validità: lista di (codice, descrizione, inizio, fine), date ISO ('' = non indicata)."""
    out = {}
    for it in fetch_specializzazioni_lookup():
        cod, desc = _coppia(it)
        if not cod: continue
        ini, fin = (_data_iso(_g(it, 'dataInizioValidita')), _data_iso(_g(it, 'dataFineValidita'))) if isinstance(it, dict) else ('', '')
        out.setdefault(cod, (cod, desc, ini, fin))
    return list(out.values())

def parse_coordinate(testo):
    """Coordinate di /api/Sedi (campo testo, formato non documentato) -> (lat, lon) oppure (None, None).
    Accetta '46.14, 12.21', '46,14;12,21', 'POINT(12.21 46.14)'; l'ordine lat/lon si deduce dall'intervallo valido per l'Italia."""
    t = _s(testo)
    if not t: return None, None
    m = re.search(r'POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)', t, re.I)
    if m: a, b = float(m.group(2)), float(m.group(1))
    else:
        nums = re.findall(r'-?\d+(?:[.,]\d+)?', t)
        if len(nums) == 4 and ',' in t and ';' not in t: nums = [nums[0] + '.' + nums[1], nums[2] + '.' + nums[3]]
        try: v = [float(x.replace(',', '.')) for x in nums[:2]]
        except ValueError: return None, None
        if len(v) < 2: return None, None
        a, b = v
    if 34 <= a <= 48 and 5 <= b <= 20: return a, b
    if 34 <= b <= 48 and 5 <= a <= 20: return b, a
    return None, None

def _get_sedi(params):
    return [r for r in _unwrap(_get(f'{config.WAUC_HTTPS}/api/Sedi', params)) if isinstance(r, dict)]

def catalogo_sedi(tipi=('CMD', 'UFC')):
    """Sedi da /api/Sedi per ciascun codTipoDipartimento: lista di (tipo, record). Se l'API rifiuta la richiesta senza searchKey
    (la descrizione Swagger la indica obbligatoria) o risponde vuoto, scansiona lettere e cifre in parallelo e toglie i doppioni.
    Solleva eccezione se WAUC non è raggiungibile."""
    out = {}
    for tipo in tipi:
        recs = None
        try: recs = _get_sedi({'codTipoDipartimento': tipo})
        except urllib.error.HTTPError: recs = None      # 400/422: serve la searchKey
        if not recs:
            def uno(k):
                try: return _get_sedi({'codTipoDipartimento': tipo, 'searchKey': k})
                except Exception as e: return e
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: risposte = list(ex.map(uno, string.ascii_lowercase + string.digits))
            buone = [r for r in risposte if isinstance(r, list)]
            if not buone: raise RuntimeError(f'WAUC non raggiungibile ({risposte[0].__class__.__name__ if risposte else "nessuna risposta"})')
            recs = [x for r in buone for x in r]
        for r in recs:
            ident = _s(_g(r, 'id')) or '|'.join(_s(_g(r, k)) for k in ('codice', 'codDistaccamento'))
            out[(tipo, ident)] = (tipo, r)
    return list(out.values())

def estrai_sede(tipo, r):
    """Record /api/Sedi -> campi della tabella sedi_wauc."""
    lat, lon = parse_coordinate(_g(r, 'coordinate'))
    tp = _g(r, 'tipologiaDistaccamento')
    return dict(id=_s(_g(r, 'id')) or '|'.join(_s(_g(r, k)) for k in ('codice', 'codDistaccamento')), codice=_s(_g(r, 'codice')), cod_distaccamento=_s(_g(r, 'codDistaccamento')),
                descrizione=_s(_g(r, 'descrizione')), tipo=_s(_g(r, 'tipo')), desc_tipo=_s(_g(r, 'descTipo')), tipo_originale=_s(_g(r, 'tipoOriginale')),
                tipologia_codice=_s(_g(tp, 'codice')) if isinstance(tp, dict) else '', tipologia_descrizione=_s(_g(tp, 'descrizione')) if isinstance(tp, dict) else '',
                provincia=_s(_g(r, 'provincia')), coordinate_raw=_s(_g(r, 'coordinate')), lat=lat, lon=lon,
                id_sede_padre=_s(_g(r, 'idSedePadre')), cod_aoo=_s(_g(r, 'codAOO')), cod_tipo_dipartimento=tipo)

def _g(d, *path):
    """Valore annidato (chiavi riconosciute senza distinguere maiuscole/underscore); '' se assente."""
    cur = d
    for k in path:
        if not isinstance(cur, dict): return ''
        cur = {norm(a): b for a, b in cur.items()}.get(norm(k))
        if cur is None: return ''
    return cur

def _s(v): return '' if v is None or isinstance(v, (dict, list)) else str(v).strip()

def catalogo_qualifiche():
    """Elenco completo delle qualifiche WAUC: (codice, cod_gruppo, descrizione, nome, cod_settore, desc_gruppo, ambito)."""
    out = {}
    for it in _unwrap(_get(f'{config.WAUC_HTTPS}/api/ElencoQualifiche')):
        if not isinstance(it, dict): continue
        cod, grp = _s(_g(it, 'codice')), _s(_g(it, 'gruppo', 'codice'))
        if cod: out[(cod, grp)] = (cod, grp, _s(_g(it, 'descrizione')), _s(_g(it, 'nome')), _s(_g(it, 'codSettore')), _s(_g(it, 'gruppo', 'descrizione')), _s(_g(it, 'gruppo', 'ambito')))
    return list(out.values())

def estrai_campi(p):
    """Normalizza un record API /api/Personale (struttura: qualifica{gruppo}, sede{...}, tipoPersonale{...}) nei campi di anagrafica_wauc."""
    q = _g(p, 'qualifica'); qs = _s(q) if not isinstance(q, dict) else ''
    return dict(
        cognome=_s(_g(p, 'cognome')), nome=_s(_g(p, 'nome')),
        account_dipvvf=_s(_g(p, 'accountDipvvf')), email_vigilfuoco=_s(_g(p, 'emailVigilfuoco')),
        cod_qualifica=_s(_g(p, 'qualifica', 'codice')), desc_qualifica=_s(_g(p, 'qualifica', 'descrizione')) or qs, nome_qualifica=_s(_g(p, 'qualifica', 'nome')),
        cod_settore=_s(_g(p, 'qualifica', 'codSettore')), cod_gruppo=_s(_g(p, 'qualifica', 'gruppo', 'codice')),
        desc_gruppo=_s(_g(p, 'qualifica', 'gruppo', 'descrizione')), ambito=_s(_g(p, 'qualifica', 'gruppo', 'ambito')),
        id_sede=_s(_g(p, 'sede', 'id')), cod_sede=_s(_g(p, 'sede', 'codice')), cod_distaccamento=_s(_g(p, 'sede', 'codDistaccamento')),
        desc_sede=_s(_g(p, 'sede', 'descrizione')), desc_sede_padre=_s(_g(p, 'sede', 'descrizionePadre')),
        turno=_s(_g(p, 'turno')), salto_turno=_s(_g(p, 'saltoTurno')),
        cod_tipo_personale=_s(_g(p, 'tipoPersonale', 'codice')), desc_tipo_personale=_s(_g(p, 'tipoPersonale', 'descrizione')))

def _dati(rec):
    """Dati per il profilo. comando_testi = testi da cui ricavare la provincia (in ordine di priorità); sede = descrizione della sede (distaccamento)."""
    ex = estrai_campi(rec)
    testi = [t for t in (ex['cod_sede'], ex['desc_sede_padre'], _campo(rec, 'comando')) if t]   # sede.codice = sigla provinciale
    return dict(nome=ex['nome'] or _campo(rec, 'nome'), cognome=ex['cognome'] or _campo(rec, 'cognome'), matricola=_campo(rec, 'matricola'), telefono=_campo(rec, 'telefono'),
                qualifica=ex['desc_qualifica'] or ex['nome_qualifica'] or ex['cod_qualifica'] or _campo(rec, 'qualifica'),
                sede=ex['desc_sede'] or _campo(rec, 'distaccamento'), comando_testi=testi, extra=ex)

def _ha_email(rec, email):
    """Email nel campo previsto (emailVigilfuoco / accountDipvvf, anche senza dominio) e, in mancanza, in qualunque valore testuale del record."""
    local = email.split('@')[0]
    for k in (_s(_g(rec, 'emailVigilfuoco')).lower(), _s(_g(rec, 'accountDipvvf')).lower()):
        if k and (k == email or k.split('@')[0] == local and ('@' not in k or k.endswith('@' + email.split('@')[1]))): return True
    vals = list(rec.values())
    for v in list(vals):
        if isinstance(v, dict): vals += list(v.values())
    return any(isinstance(v, str) and v.strip().lower() == email for v in vals)

def _trova(recs, email, local):
    """('email', rec) se l'email corrisponde; ('nome', rec) se nella sede c'è un'unica corrispondenza nome.cognome; altrimenti None."""
    for r in recs:
        if _ha_email(r, email): return 'email', r
    cand = [r for r in recs if local and local in (norm(_s(_g(r, 'nome')) + _s(_g(r, 'cognome'))), norm(_s(_g(r, 'cognome')) + _s(_g(r, 'nome'))))]
    return ('nome', cand[0]) if len(cand) == 1 else None

def _esito(via, r, sede): return dict(dati=_dati(r), specs=_specs(r), sede=sede, via=via)

def cerca_persona(email, sedi=None, prima=None):
    """Cerca l'email nelle sedi indicate (default config.WAUC_SEDI), in parallelo. `prima` = sede già nota, provata per prima (1 sola richiesta).
    None se non trovata. Altrimenti dict(dati, specs, sede, via) con via='email' o 'nome' (corrispondenza nome.cognome, accettata solo se unica in tutte le sedi).
    Solleva eccezione se l'API non è raggiungibile per tutte le sedi."""
    email = email.strip().lower(); local = norm(email.split('@')[0]); errori = []; ok = False; per_nome = []
    sedi = list(sedi if sedi is not None else config.WAUC_SEDI)
    if prima:
        try:
            recs = fetch_personale(prima); ok = True; t = _trova(recs, email, local)
            if t and t[0] == 'email': return _esito('email', t[1], prima)
        except Exception as e: errori.append(f'{prima}: {e.__class__.__name__}')
    resto = [s for s in sedi if s != prima]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_personale if len(resto) == 1 else _fetch, s): s for s in resto}
        for f in concurrent.futures.as_completed(futs):
            s = futs[f]
            try: recs = f.result(); ok = True
            except Exception as e:
                errori.append(f'{s}: {e.__class__.__name__}')
                if not ok and len(errori) >= 8:   # nessuna sede risponde: WAUC non raggiungibile, inutile insistere su tutte le altre
                    for p in futs: p.cancel()
                    break
                continue
            t = _trova(recs, email, local)
            if t and t[0] == 'email':
                _cache[s] = (time.time(), recs)
                for p in futs: p.cancel()
                return _esito('email', t[1], s)
            if t: per_nome.append((t[1], s))
    if len(per_nome) == 1: return _esito('nome', per_nome[0][0], per_nome[0][1])
    if not ok and errori: raise RuntimeError('WAUC non raggiungibile (' + '; '.join(errori[:3]) + ')')
    return None
