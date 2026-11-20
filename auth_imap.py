"""Autenticazione con credenziali dipartimentali (server di posta IMAP VVF, raggiungibile solo in rete VVF o con FortiClient VPN).
La password viene solo verificata dal server di posta: PUMA non la salva mai e non la scrive nei registri."""
import imaplib, logging, socket, re, ssl
import config

log = logging.getLogger('accesso')


def norm_email(raw):
    """Accetta 'nome.cognome' oppure 'nome.cognome@vigilfuoco.it': il dominio viene aggiunto se manca (e non raddoppiato se già scritto).
    Ritorna (email, errore)."""
    raw = (raw or '').strip().lower().replace(' ', '')
    suffisso = '@' + config.DOMINIO
    while raw.endswith(suffisso): raw = raw[:-len(suffisso)]
    local, sep, dom = raw.partition('@')
    if sep: return None, f'usa un indirizzo @{config.DOMINIO}'
    if not re.match(r'^[a-z0-9._-]+$', local): return None, 'indirizzo non valido (atteso nome.cognome)'
    return local + suffisso, None


EMAIL_RE = re.compile(r'^[a-z0-9._-]+@' + re.escape(config.DOMINIO) + r'$')

VPN_MSG = ('server di posta dipartimentale non raggiungibile ({}). Controlla che FortiClient VPN sia collegata '
           '(o di essere sulla rete VVF) e riprova.')


def _testo(e):
    """Messaggio leggibile di un errore IMAP (il server risponde con bytes tipo b'[AUTHENTICATIONFAILED] ...')."""
    t = str(e)
    m = re.match(r"^b'(.*)'$", t)
    return (m.group(1) if m else t)[:200]


def verifica(email, password):
    """(ok, messaggio per l'utente, dettaglio tecnico per il registro). Il dettaglio non contiene mai la password."""
    if not EMAIL_RE.match(email) or not password or any(c in password for c in '\r\n\x00'):
        return False, 'Credenziali non valide', 'utente o password vuoti o non validi'
    if config.DEV_AUTH:
        ok = password == 'dev'
        return ok, (None if ok else 'Credenziali non valide (modalità prova: la password è «dev»)'), 'modalità prova'
    utente = email if config.IMAP_UTENTE == 'email' else email.split('@')[0]
    try:
        m = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT, timeout=config.IMAP_TIMEOUT)
    except socket.timeout:
        return False, VPN_MSG.format('tempo scaduto'), f'connessione a {config.IMAP_HOST}:{config.IMAP_PORT}: tempo scaduto'
    except socket.gaierror:
        return False, VPN_MSG.format('indirizzo sconosciuto'), f'{config.IMAP_HOST} non si risolve (DNS della VPN?)'
    except ssl.SSLError as e:
        return False, f'collegamento sicuro con il server di posta non riuscito ({e.__class__.__name__}).', f'TLS: {e}'
    except OSError as e:
        return False, VPN_MSG.format(e.__class__.__name__), f'connessione: {e}'
    try:
        try:
            typ, dati = m.login(utente, password)
        except imaplib.IMAP4.error as e:
            return False, 'Credenziali non valide: controlla nome.cognome e la password della posta dipartimentale.', f'login rifiutato come «{utente}»: {_testo(e)}'
        except UnicodeError:
            return False, 'La password contiene caratteri non accettati dal server di posta.', 'password con caratteri non ASCII'
        if typ == 'OK': return True, None, f'login OK come «{utente}»'
        return False, 'Login rifiutato dal server di posta.', f'risposta {typ}: {dati!r}'[:200]
    except (socket.timeout, OSError) as e:
        return False, VPN_MSG.format(e.__class__.__name__), f'durante il login: {e}'
    finally:
        try: m.logout()
        except Exception: pass


def autentica(email, password):
    """(True, None) se valide, altrimenti (False, messaggio). Il motivo tecnico finisce nel registro e nella finestra di PUMA."""
    ok, msg, dettaglio = verifica(email, password)
    (log.info if ok else log.warning)('Accesso %s per %s: %s', 'riuscito' if ok else 'NEGATO', email, dettaglio)
    return ok, msg


def estrai_nome_cognome(email):
    parts = email.split('@')[0].split('.')
    return parts[0].capitalize(), ' '.join(p.capitalize() for p in parts[1:])
