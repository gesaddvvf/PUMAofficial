"""Utenti non VVF (v1.5): Amministrazioni dello Stato, Forze armate e di polizia, volontariato, Croce Rossa, CNSAS…

Si registrano da soli (/registrazione) e accedono con CODICE FISCALE e PASSWORD scelta (salvata solo come hash).
Funzioni limitate: Partecipa ad addestramento (anche dal link d'invito), Report individuale e Area personale.
Li abilita l'Amministratore del Comando scelto (Area Comando → Livelli di accesso); chi si registra dal link d'invito
di un addestramento è abilitato subito.
SPID / CIE: richiedono che PUMA sia un servizio accreditato (AgID / Ministero dell'Interno) su un indirizzo https pubblico;
la funzione `entra_con_identita()` è il punto in cui collegarli quando PUMA sarà ospitato sui server del Dipartimento."""
import re, secrets
from werkzeug.security import generate_password_hash, check_password_hash

ENTI = ['Amministrazione dello Stato', 'Esercito Italiano', 'Marina Militare', 'Aeronautica Militare', 'Arma dei Carabinieri',
        'Polizia di Stato', 'Guardia di Finanza', 'Polizia Locale', 'Protezione Civile', 'Volontariato di Protezione Civile',
        'Croce Rossa Italiana', 'Soccorso Alpino e Speleologico (CNSAS)', 'Servizio sanitario / 118', 'Vigili del Fuoco volontari (TN, BZ, AO)',
        'Ente locale', 'Altro']
DOMINIO_INTERNO = 'esterno.puma'   # username interno: <codice fiscale>@esterno.puma (non è una casella di posta)

_DISPARI = dict(zip("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))


def norm_cf(cf):
    """Toglie tutti gli spazi (anche quelli finali incollati per errore) e mette in maiuscolo."""
    return re.sub(r'\s+', '', cf or '').upper()


def cf_valido(cf):
    cf = norm_cf(cf)
    if not re.fullmatch(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPR-T][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]", cf): return False
    tot = sum(_DISPARI[ch] if i % 2 == 0 else (int(ch) if ch.isdigit() else ord(ch) - 65) for i, ch in enumerate(cf[:15]))
    return cf[15] == chr(65 + tot % 26)


def sembra_cf(testo):
    return bool(re.fullmatch(r'[A-Za-z0-9]{16}', norm_cf(testo)))


def username(cf):
    return f'{norm_cf(cf).lower()}@{DOMINIO_INTERNO}'


def password_ok(p):
    """Almeno 10 caratteri con lettere e numeri."""
    if len(p or '') < 10: return 'La password deve avere almeno 10 caratteri.'
    if not re.search(r'[A-Za-z]', p) or not re.search(r'\d', p): return 'La password deve contenere lettere e numeri.'
    return None


def hash_password(p): return generate_password_hash(p)
def verifica_password(h, p): return bool(h) and check_password_hash(h, p or '')
def password_temporanea(): return 'Puma-' + secrets.token_urlsafe(6) + str(secrets.randbelow(90) + 10)


def entra_con_identita(*_):
    """Aggancio per SPID / CIE (non attivo: serve l'accreditamento del servizio)."""
    raise NotImplementedError('SPID e CIE richiedono PUMA accreditato come fornitore di servizi su un indirizzo https pubblico.')
