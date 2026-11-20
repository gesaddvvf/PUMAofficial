"""WAUC simulato per la modalità prova: risponde alle stesse chiamate dell'API reale leggendo prova/wauc_finto.json.
Viene usato da wauc._get() quando config.WAUC_FINTO è attivo, quindi il resto del programma (ricerca della persona,
lettura di qualifica, sede, specializzazioni...) funziona esattamente come con il WAUC vero."""
import copy, json, os, urllib.error, urllib.parse

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wauc_finto.json')
_dati = None


def dati():
    global _dati
    if _dati is None:
        with open(FILE, encoding='utf-8') as f: _dati = json.load(f)
    return _dati


def risposta(url, params):
    percorso = urllib.parse.urlparse(url).path.rstrip('/').lower()
    d = dati()
    if percorso.endswith('/api/personale'):
        sedi = {s.strip().upper() for s in str(params.get('codiciSede', '')).split(',') if s.strip()}
        return copy.deepcopy([p for p in d['personale'] if not sedi or p['sede']['codice'].upper() in sedi])
    if percorso.endswith('/api/specializzazioni'):
        return copy.deepcopy(d['specializzazioni'])
    if percorso.endswith('/api/elencoqualifiche'):
        return copy.deepcopy(d['qualifiche'])
    if percorso.endswith('/api/sedi'):
        tipo = str(params.get('codTipoDipartimento', '')).upper()
        chiave = str(params.get('searchKey', '')).lower()
        return copy.deepcopy([s for s in d['sedi'] if (not tipo or s['tipo'] == tipo) and chiave in s['descrizione'].lower()])
    raise urllib.error.HTTPError(url, 404, 'WAUC simulato: indirizzo non previsto', None, None)
