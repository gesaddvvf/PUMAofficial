"""Verifica dei collegamenti alla rete VVF: server di posta (login) e WAUC (dati del personale).
Entrambi sono raggiungibili solo dalla rete interna VVF oppure da fuori con FortiClient VPN collegata.
Usato dalla pagina di accesso (/stato-rete) e da  python manage.py verifica-vpn."""
import socket, time, threading, urllib.parse
from flask import jsonify
import config

_cache = {'t': 0, 'dati': None}
_lock = threading.Lock()


def prova_porta(host, porta, timeout=3):
    """(ok, dettaglio): risoluzione del nome e apertura della connessione TCP."""
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return False, f'il nome {host} non si risolve (rete VVF non raggiungibile: VPN scollegata?)'
    try:
        with socket.create_connection((ip, porta), timeout=timeout):
            return True, f'{host}:{porta} raggiungibile ({ip})'
    except socket.timeout:
        return False, f'{host}:{porta} non risponde (tempo scaduto)'
    except OSError as e:
        return False, f'{host}:{porta} non raggiungibile ({e.__class__.__name__})'


def _host_porta(url):
    u = urllib.parse.urlparse(url)
    return u.hostname, u.port or (443 if u.scheme == 'https' else 80)


def controlli(timeout=3):
    """Lista di dict(nome, ok, dettaglio, serve_per) per posta e WAUC, eseguiti in parallelo."""
    voci = [('Posta dipartimentale', config.IMAP_HOST, config.IMAP_PORT, 'accesso con le credenziali dipartimentali')]
    visti = set()
    for url in (config.WAUC_HTTP, config.WAUC_HTTPS):
        h, p = _host_porta(url)
        if h and (h, p) not in visti:
            visti.add((h, p)); voci.append((f'WAUC ({"https" if p == 443 else "http"})', h, p, 'dati del personale (profilo, qualifica, specializzazioni)'))
    out = [None] * len(voci)

    def uno(i, v):
        ok, det = prova_porta(v[1], v[2], timeout)
        out[i] = dict(nome=v[0], ok=ok, dettaglio=det, serve_per=v[3])
    th = [threading.Thread(target=uno, args=(i, v)) for i, v in enumerate(voci)]
    for t in th: t.start()
    for t in th: t.join()
    return out


def stato_json():
    """Risposta per la pagina di accesso (in cache 30 secondi per non rallentare)."""
    if config.PROVA:
        return jsonify(modalita='prova', messaggio='Modalità prova: utenti fittizi e dati WAUC simulati, nessun collegamento alla rete VVF necessario.')
    with _lock:
        if not _cache['dati'] or time.time() - _cache['t'] > 30:
            _cache['dati'], _cache['t'] = controlli(timeout=2), time.time()
        dati = _cache['dati']
    return jsonify(modalita='reale', controlli=dati, tutto_ok=all(c['ok'] for c in dati),
                   login_ok=dati[0]['ok'] or config.DEV_AUTH)
