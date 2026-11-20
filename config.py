"""Configurazione di P.U.M.A. (Piattaforma Unificata Monitoraggio Addestramenti).

Due modalità di funzionamento:
  - reale  (default)       login con le credenziali dipartimentali (posta IMAP) e dati del personale da WAUC.
                           Serve la rete VVF: da casa o fuori sede con FortiClient VPN attiva.
  - prova  (PUMA_MODALITA=prova)  utenti fittizi, password «dev», WAUC simulato (prova/wauc_finto.json),
                           db separato in data_prova/. Funziona senza VPN e senza Internet.

Le impostazioni si possono scrivere nel file puma.env (una per riga, NOME=valore; vedi puma.env.esempio)
oppure come variabili d'ambiente. Per compatibilità sono accettati anche i vecchi nomi PORTALE_*.
Tutto ciò che è dato (db, chiave della sessione, backup, documenti) vive nella cartella dati e NON
viene mai sovrascritto dagli aggiornamenti: si sostituiscono tutti i file tranne data/ e data_prova/."""
import os, sys, secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for _flusso in (sys.stdout, sys.stderr):   # console di Windows: mai errori per caratteri non rappresentabili
    try: _flusso.reconfigure(errors='replace')
    except Exception: pass
# Librerie incluse (libs/, solo Python puro): nessuna installazione, funziona anche senza accesso a PyPI
sys.path.insert(0, os.path.join(BASE_DIR, 'libs'))


def _carica_env(percorso):
    """Legge puma.env (NOME=valore, # per i commenti). Le variabili già impostate nel sistema hanno la precedenza."""
    if not os.path.exists(percorso): return
    with open(percorso, encoding='utf-8-sig') as f:
        for riga in f:
            riga = riga.strip()
            if not riga or riga.startswith('#') or '=' not in riga: continue
            k, v = riga.split('=', 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'': v = v[1:-1]
            if k: os.environ.setdefault(k, v)


_carica_env(os.path.join(BASE_DIR, 'puma.env'))


def env(nome, default=None):
    """PUMA_<nome>, oppure il vecchio PORTALE_<nome>, oppure default."""
    for pref in ('PUMA_', 'PORTALE_'):
        v = os.environ.get(pref + nome)
        if v is not None and v != '': return v
    return default


NOME_APP = 'P.U.M.A.'
NOME_ESTESO = 'Piattaforma Unificata Monitoraggio Addestramenti'
VERSIONE = "1.4.0"

MODALITA = 'prova' if env('MODALITA', 'reale').strip().lower() == 'prova' else 'reale'
PROVA = MODALITA == 'prova'

# Modulo che si apre subito dopo il login. Altri moduli in moduli/ restano disponibili da «App» nel menu.
MODULO_PRINCIPALE = env('MODULO_PRINCIPALE', 'puma')

DATA_DIR = env('DATA', os.path.join(BASE_DIR, 'data_prova' if PROVA else 'data'))
DB_PATH = os.path.join(DATA_DIR, 'puma.db')
BACKUP_DIR = os.path.join(DATA_DIR, 'backup')

# Rete: di default PUMA è raggiungibile solo da questo PC. PUMA_HOST=0.0.0.0 per aprirlo agli altri PC della rete.
HOST, PORT = env('HOST', '127.0.0.1'), int(env('PORT', 8080))

# Login con le credenziali dipartimentali (server di posta raggiungibile solo in rete VVF / VPN)
IMAP_HOST, IMAP_PORT, IMAP_TIMEOUT = env('IMAP_HOST', 'imap-s.vigilfuoco.it'), int(env('IMAP_PORT', 993)), int(env('IMAP_TIMEOUT', 10))
DOMINIO = 'vigilfuoco.it'
# Come presentarsi al server di posta: 'email' (nome.cognome@vigilfuoco.it, default) oppure 'nome' (solo nome.cognome)
IMAP_UTENTE = 'nome' if env('IMAP_UTENTE', 'email').strip().lower() == 'nome' else 'email'
# Password «dev» per qualsiasi utente: sempre attiva in modalità prova, MAI in uso reale.
DEV_AUTH = PROVA or env('DEV_AUTH') == '1'

# Anagrafica del personale (WAUC, rete VVF / VPN). In modalità prova si usa il WAUC simulato.
WAUC_FINTO = PROVA or env('WAUC_FINTO') == '1'
WAUC_ATTIVO = WAUC_FINTO or env('WAUC', '1') == '1'
WAUC_HTTP = env('WAUC_HTTP', 'http://wauc.dipvvf.it')
WAUC_HTTPS = env('WAUC_HTTPS', 'https://wauc.dipvvf.it')
# Sedi in cui cercare la persona al login (sigle provinciali, es. FC,RA). Vuoto = tutte (più lento la prima volta).
WAUC_SEDI = [s.strip().upper() for s in env('WAUC_SEDI', '').split(',') if s.strip()]
WAUC_TIMEOUT = int(env('WAUC_TIMEOUT', 8))
WAUC_VERIFY_SSL = env('WAUC_VERIFY_SSL', '1') == '1'

os.makedirs(BACKUP_DIR, exist_ok=True)
LOG_PATH = os.path.join(DATA_DIR, 'puma.log')


def avvia_log():
    """Messaggi di PUMA (accessi riusciti e negati con il motivo, errori WAUC...) nella finestra e in <dati>/puma.log."""
    import logging, logging.handlers
    radice = logging.getLogger()
    if any(getattr(h, '_puma', False) for h in radice.handlers): return
    fmt = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s', '%Y-%m-%d %H:%M:%S')
    for h in (logging.StreamHandler(), logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding='utf-8')):
        h.setFormatter(fmt); h._puma = True; radice.addHandler(h)
    radice.setLevel(logging.INFO)


def secret_key():
    p = os.path.join(DATA_DIR, 'secret.key')
    if not os.path.exists(p):
        with open(p, 'w') as f: f.write(secrets.token_hex(32))
        try: os.chmod(p, 0o600)
        except OSError: pass
    with open(p) as f: return f.read().strip()
