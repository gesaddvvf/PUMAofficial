"""Livelli di accesso di P.U.M.A. (v1.3).

Ogni persona ha uno o più ruoli; ogni ruolo vale per una SEDE e per un'AREA CORSI:
  - ruoli «Direzione»: la sede è una Direzione Regionale e valgono per la DR e per tutti i suoi Comandi;
  - ruoli «Comando": la sede è un Comando;
  - Amministratore Generale: tutta Italia; Operatore: nessun permesso aggiuntivo (è il livello di tutti).
  - area corsi: un codice di puma_settori (SAF, TPSS, NBCR…) oppure '*' = tutte le aree.

COSA PUÒ FARE OGNI RUOLO: è tutto in MATRICE qui sotto. È PROVVISORIA: va aggiornata quando saranno definiti
i compiti di ciascun livello. Cambiando MATRICE cambiano subito menu, pagine e controlli (niente da toccare altrove).
"""
import datetime

# capacità: (descrizione, vale per area corsi?)
CAPACITA = {
    'partecipa':    ('Partecipa agli addestramenti e registra le proprie attività', False),
    'area_comando': ("Apre l'Area Comando", False),
    'report':       ('Report collettivo e cruscotto corsi', True),
    'programma':    ('Programma addestramenti collettivi', True),
    'piano':        ('Piano di sicurezza e convalida delle presenze', True),
    'documenti':    ('Carica documentazione e materiale didattico', True),
    'localita':     ('Gestisce il database località', False),
    'magazzino':    ('Magazzino (modulo in arrivo)', True),
    'impostazioni': ('Impostazioni della sede (mail, validità, manovre)', False),
    'ruoli':        ('Assegna i livelli di accesso e invita colleghi', False),
    'aree':         ('Gestisce le aree corsi e importa il foglio PUMA', False),
    'sistema':      ('Configurazione, WAUC, utenti, Comandi e registro attività', False),
}
_TUTTO = list(CAPACITA)
_GESTIONE = ['partecipa', 'area_comando', 'report', 'programma', 'piano', 'documenti', 'localita', 'magazzino', 'impostazioni', 'ruoli']
_FUNZ = ['partecipa', 'area_comando', 'report', 'programma', 'piano', 'documenti', 'localita']
_RESP = ['partecipa', 'area_comando', 'report', 'programma', 'piano', 'localita']
_STAFF = ['partecipa', 'area_comando', 'programma', 'piano', 'localita']
_MAG = ['partecipa', 'area_comando', 'magazzino']

MATRICE = {   # PROVVISORIA
    'AMM_GEN': _TUTTO,
    'AMM_DIR': _GESTIONE, 'FUNZ_DIR': _FUNZ, 'ROR_DIR': _RESP, 'STAFF_DIR': _STAFF, 'MAG_DIR': _MAG,
    'AMM_CMD': _GESTIONE, 'FUNZ_CMD': _FUNZ, 'ROP_CMD': _RESP, 'STAFF_CMD': _STAFF, 'MAG_CMD': _MAG,
    'OPERATORE': ['partecipa'],
    'ESTERNO': ['partecipa'],   # utente non VVF: solo partecipazione e report individuale (vedi app.ESTERNI_OK)
}
# chi può assegnare quali ruoli (oltre all'Amministratore Generale, che assegna tutto)
ASSEGNA = {
    'AMM_DIR': ['FUNZ_DIR', 'ROR_DIR', 'STAFF_DIR', 'MAG_DIR', 'AMM_CMD', 'FUNZ_CMD', 'ROP_CMD', 'STAFF_CMD', 'MAG_CMD', 'OPERATORE'],
    'AMM_CMD': ['FUNZ_CMD', 'ROP_CMD', 'STAFF_CMD', 'MAG_CMD', 'OPERATORE'],
}


def ruoli(c):
    return c.execute('SELECT * FROM puma_ruoli ORDER BY ordine').fetchall()


def aree(c, tutte=False):
    return c.execute('SELECT * FROM puma_settori ' + ('' if tutte else 'WHERE attiva=1 ') + 'ORDER BY ordine, nome').fetchall()


def assegnazioni(c, uid):
    """Ruoli della persona, con livello, nome della sede e direzione della sede."""
    return c.execute("""SELECT a.*, r.nome AS ruolo_nome, r.livello, r.ordine, k.nome AS sede_nome, k.tipo AS sede_tipo,
            cd.direzione_id, COALESCE(s.nome, 'Tutte le aree') AS area_nome
        FROM puma_ruoli_utente a JOIN puma_ruoli r ON r.codice=a.ruolo LEFT JOIN comandi k ON k.id=a.sede_id
        LEFT JOIN puma_comando_dir cd ON cd.comando_id=a.sede_id LEFT JOIN puma_settori s ON s.codice=a.settore
        WHERE a.utente_id=? ORDER BY r.ordine, k.nome, a.settore""", (uid,)).fetchall()


def sedi_di(c, a):
    """Sedi coperte da un'assegnazione: None = tutte."""
    if a['livello'] == 'nazionale': return None
    if a['livello'] == 'direzione':
        if not a['direzione_id']: return [a['sede_id']]
        return [r[0] for r in c.execute('SELECT comando_id FROM puma_comando_dir WHERE direzione_id=?', (a['direzione_id'],))]
    if a['livello'] == 'comando': return [a['sede_id']]
    return []


class Accessi:
    """Permessi calcolati di una persona (si crea una volta per richiesta)."""
    def __init__(self, c, utente):
        self.u = utente
        self.righe = list(assegnazioni(c, utente['id'])) if utente else []
        self._sedi = [(a, sedi_di(c, a)) for a in self.righe]
        self.admin = bool(utente and utente['is_admin']) or any(a['ruolo'] == 'AMM_GEN' for a in self.righe)

    def puo(self, cap, settore=None, sede=None):
        """cap = chiave di CAPACITA; settore = area corsi (None = qualsiasi); sede = id comando (None = qualsiasi)."""
        if self.admin: return True
        if cap == 'partecipa': return True
        area = CAPACITA.get(cap, ('', False))[1]
        for a, sedi in self._sedi:
            if cap not in MATRICE.get(a['ruolo'], ()): continue
            if area and settore and a['settore'] not in ('*', (settore or '').upper()): continue
            if sede is not None and sedi is not None and sede not in sedi: continue
            return True
        return False

    def sedi(self, cap):
        """Sedi dove la persona ha la capacità: None = tutte, [] = nessuna."""
        if self.admin: return None
        out = set()
        for a, sedi in self._sedi:
            if cap in MATRICE.get(a['ruolo'], ()):
                if sedi is None: return None
                out.update(sedi)
        return sorted(out)

    def aree(self, cap):
        """Aree corsi in cui la persona ha la capacità: None = tutte."""
        if self.admin: return None
        out = set()
        for a, _ in self._sedi:
            if cap in MATRICE.get(a['ruolo'], ()):
                if a['settore'] == '*': return None
                out.add(a['settore'])
        return sorted(out)

    def livello_visibilita(self):
        """comando | regione | nazionale, per i report (compatibile con puma_livello_utente)."""
        if self.admin: return 'nazionale'
        if any(a['livello'] == 'direzione' and 'report' in MATRICE.get(a['ruolo'], ()) for a in self.righe): return 'regione'
        return 'comando'

    def assegnabili(self):
        """Ruoli che la persona può assegnare."""
        if self.admin: return list(MATRICE)
        out = []
        for a in self.righe:
            for r in ASSEGNA.get(a['ruolo'], ()):
                if r not in out: out.append(r)
        return out

    def etichetta(self):
        """Ruolo principale da mostrare (il più alto)."""
        if not self.righe: return 'Amministratore Generale' if self.admin else 'Operatore'
        a = self.righe[0]
        dove = f" · {a['sede_nome']}" if a['sede_nome'] else ''
        return a['ruolo_nome'] + ('' if a['settore'] == '*' else f" {a['settore']}") + dove


def assegna(c, uid, ruolo, sede_id, settore, da):
    settore = (settore or '*').upper() if settore != '*' else '*'
    c.execute("""INSERT OR IGNORE INTO puma_ruoli_utente(utente_id, ruolo, sede_id, settore, assegnato_da, assegnato_il)
        VALUES(?,?,?,?,?,?)""", (uid, ruolo, sede_id, settore, da, datetime.datetime.now().isoformat(timespec='seconds')))
    if ruolo == 'AMM_GEN': c.execute('UPDATE utenti SET is_admin=1 WHERE id=?', (uid,))


def togli(c, rid):
    r = c.execute('SELECT * FROM puma_ruoli_utente WHERE id=?', (rid,)).fetchone()
    if not r: return None
    c.execute('DELETE FROM puma_ruoli_utente WHERE id=?', (rid,))
    if r['ruolo'] == 'AMM_GEN' and not c.execute("SELECT 1 FROM puma_ruoli_utente WHERE utente_id=? AND ruolo='AMM_GEN'", (r['utente_id'],)).fetchone():
        c.execute('UPDATE utenti SET is_admin=0 WHERE id=?', (r['utente_id'],))
    return r


def accessi():
    """Accessi dell'utente della richiesta corrente (cache in flask.g)."""
    from flask import g
    import db as portale_db
    if 'puma_accessi' not in g:
        with portale_db.connect() as c: g.puma_accessi = Accessi(c, g.get('utente'))
    return g.puma_accessi


def applica_inviti(c, utente):
    """Al login: se c'è un invito valido per questa email, l'account diventa attivo con Comando e ruolo dell'invito."""
    oggi = datetime.date.today().isoformat()
    inv = c.execute("""SELECT * FROM puma_inviti WHERE lower(email)=lower(?) AND usato_il IS NULL AND (scade_il IS NULL OR scade_il>=?)
        ORDER BY creato_il""", (utente['email'], oggi)).fetchall()
    if not inv: return False
    adesso = datetime.datetime.now().isoformat(timespec='seconds')
    for i in inv:
        if i['comando_id'] and not utente['comando_id']: c.execute('UPDATE utenti SET comando_id=? WHERE id=?', (i['comando_id'], utente['id']))
        assegna(c, utente['id'], i['ruolo'] or 'OPERATORE', i['sede_id'], i['settore'] or '*', 'invito di ' + (i['creato_da'] or ''))
        c.execute('UPDATE puma_inviti SET usato_il=? WHERE token=?', (adesso, i['token']))
    if utente['stato'] == 'in_attesa':
        c.execute("UPDATE utenti SET stato='attivo', approvato_il=? WHERE id=?", (adesso, utente['id']))
    return True


def applica_invito_evento(c, utente, percorso, ruolo='OPERATORE'):
    """Al login da un link d'invito di un addestramento (/puma/i/<token>): chi è in attesa diventa Operatore
    (è personale VVF: la password dipartimentale è già stata verificata) e può aprire l'addestramento."""
    import re
    m = re.fullmatch(r'/puma/i/([A-Za-z0-9]+)', percorso or '')
    if not m or not c.execute('SELECT 1 FROM puma_eventi WHERE invito_token=?', (m.group(1),)).fetchone(): return False
    if utente['stato'] != 'in_attesa': return False
    assegna(c, utente['id'], ruolo, None, '*', 'invito addestramento')
    c.execute("UPDATE utenti SET stato='attivo', approvato_il=? WHERE id=?", (datetime.datetime.now().isoformat(timespec='seconds'), utente['id']))
    return True
