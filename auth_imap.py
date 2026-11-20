"""Autenticazione con credenziali dipartimentali (server di posta IMAP VVF, raggiungibile solo in rete VVF o con FortiClient VPN).
La password viene solo verificata dal server di posta: PUMA non la salva mai."""
import imaplib, socket, re
import config
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

def autentica(email, password):
    """(True, None) se valide, altrimenti (False, messaggio)."""
    if not EMAIL_RE.match(email) or not password or any(c in password for c in '\r\n\x00'):
        return False, 'Credenziali non valide'
    if config.DEV_AUTH:
        return (password == 'dev'), (None if password == 'dev' else 'Credenziali non valide (modalità sviluppo)')
    try:
        m = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT, timeout=config.IMAP_TIMEOUT)
        try: typ, _ = m.login(email, password)
        finally:
            try: m.logout()
            except Exception: pass
        return (True, None) if typ == 'OK' else (False, 'Login rifiutato dal server')
    except (imaplib.IMAP4.error, UnicodeError): return False, 'Credenziali non valide'
    except socket.timeout: return False, VPN_MSG.format('tempo scaduto')
    except socket.gaierror: return False, VPN_MSG.format('indirizzo sconosciuto')
    except OSError as e: return False, VPN_MSG.format(e.__class__.__name__)

VPN_MSG = ('server di posta dipartimentale non raggiungibile ({}). Controlla che FortiClient VPN sia collegata '
           '(o di essere sulla rete VVF) e riprova.')

def estrai_nome_cognome(email):
    parts = email.split('@')[0].split('.')
    return parts[0].capitalize(), ' '.join(p.capitalize() for p in parts[1:])
